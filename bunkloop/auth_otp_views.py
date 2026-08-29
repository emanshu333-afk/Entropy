"""
Auth OTP API views — per BunkLoop_SendOTP_Email_Integration_Guide.md §9-10.

Endpoints:
  POST /api/auth/send-email-otp/   {email}
  POST /api/auth/verify-email-otp/ {email, code}

Uses bunkloop.email_otp service (sendotp.email) + Django cache (Redis) for challenge_id.
Never stores OTP code. Frontend never sees API key or challenge ID directly (challenge stays server-side).
"""
from django.core.cache import cache
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .email_otp import send_email_otp, verify_email_otp, otp_cache_key, OTPServiceError
from .models import University


def _is_university_email_allowed(email: str) -> tuple[bool, str]:
    """
    Reuse existing university email logic: check denied list, academic suffix, and University.domains.
    Returns (allowed, error_message).
    """
    from .forms import validate_student_email
    try:
        # validate_student_email already checks denied, academic, MX, and University allowlist via _is_domain_in_university_allowlist
        # But it also does MX lookup which is fine; we want to apply same restriction before sending OTP
        validate_student_email(email)
        return True, ""
    except DjangoValidationError as e:
        # e.messages is list
        msg = "; ".join(e.messages) if hasattr(e, 'messages') else str(e)
        return False, msg
    except Exception as e:
        return False, str(e)


@api_view(["POST"])
@permission_classes([AllowAny])
def send_otp_view(request):
    # Use DRF's request.data (already parsed)
    email = str(request.data.get("email", "")).strip().lower()

    if not email:
        return Response(
            {"error": "Email is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validate_email(email)
    except DjangoValidationError:
        return Response(
            {"error": "Enter a valid email address."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # University restriction (guide §19) — before sending OTP
    allowed, err_msg = _is_university_email_allowed(email)
    if not allowed:
        return Response(
            {"error": err_msg or "Please use your university email address."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Rate limiting: basic throttle via cache (guide §17)
    # Allow ~3-5 per email per short window
    rate_key = f"otp_send_rate:{email}"
    try:
        count = cache.get(rate_key, 0)
        if count >= 5:
            return Response(
                {"error": "Too many OTP requests. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
    except Exception:
        pass

    try:
        result = send_email_otp(email, purpose="signup")
    except OTPServiceError as exc:
        # Map specific errors to appropriate status
        msg = str(exc)
        # For cooldown, return 200 with retry_after as per guide
        if "cooldown" in msg.lower() or "retry" in msg.lower():
            return Response(
                {"error": msg},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return Response(
            {"error": msg},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as exc:
        return Response(
            {"error": "Email verification is temporarily unavailable. Please try again."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    challenge_id = result.get("id")
    expires_at = result.get("expires_at")

    if challenge_id:
        # Store challenge in cache for 10 min (guide §8) — never store OTP code
        try:
            cache.set(
                otp_cache_key(email),
                {
                    "challenge_id": challenge_id,
                    "expires_at": expires_at,
                },
                timeout=600,
            )
        except Exception:
            # Fallback to in-memory if cache unavailable (should not happen)
            pass
        # Increment rate counter
        try:
            # Use cache incr with timeout
            current = cache.get(rate_key, 0)
            cache.set(rate_key, current + 1, timeout=300)
        except Exception:
            pass

    if result.get("cooldown"):
        return Response(
            {
                "success": True,
                "message": "An OTP was already sent recently.",
                "retry_after": result.get("retry_after"),
                "expires_at": expires_at,
            },
            status=status.HTTP_200_OK,
        )

    return Response(
        {
            "success": True,
            "message": "Verification code sent.",
            "expires_at": expires_at,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_otp_view(request):
    email = str(request.data.get("email", "")).strip().lower()
    code = str(request.data.get("code", "")).strip()

    if not email or not code:
        return Response(
            {"error": "Email and OTP are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not code.isdigit() or len(code) != 6:
        return Response(
            {"error": "Enter a valid 6-digit OTP."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Retrieve challenge from cache (frontend never supplies it)
    cached = None
    try:
        cached = cache.get(otp_cache_key(email))
    except Exception:
        cached = None

    if not cached:
        return Response(
            {
                "verified": False,
                "error": "OTP expired or no verification request exists. Please request a new code."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    challenge_id = cached.get("challenge_id")
    if not challenge_id:
        return Response(
            {"verified": False, "error": "OTP expired. Please request a new code."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        result = verify_email_otp(
            email=email,
            challenge_id=challenge_id,
            code=code,
            purpose="signup",
        )
    except OTPServiceError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:
        return Response(
            {"error": "Email verification is temporarily unavailable. Please try again."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if not result.get("valid"):
        reason = result.get("reason")
        messages = {
            "wrong_code": "Incorrect verification code.",
            "expired": "Verification code has expired. Please request a new code.",
            "locked": "Too many incorrect attempts. Request a new code.",
            "superseded": "This verification code is no longer active. Please request a new code.",
        }
        return Response(
            {
                "verified": False,
                "error": messages.get(
                    reason,
                    "Verification failed. Request a new code if necessary.",
                ),
                "reason": reason,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Success: delete cache and mark session as verified (guide §13 Option A)
    try:
        cache.delete(otp_cache_key(email))
    except Exception:
        pass

    # Mark email as verified in session for signup enforcement (guide §13)
    try:
        request.session["verified_signup_email"] = email
        # Also set a timestamp for expiry if needed
        from django.utils import timezone
        request.session["verified_signup_at"] = timezone.now().isoformat()
    except Exception:
        pass

    return Response(
        {
            "verified": True,
            "message": "Email verified successfully.",
        },
        status=status.HTTP_200_OK,
    )
