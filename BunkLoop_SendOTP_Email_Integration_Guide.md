# BunkLoop — Email OTP Verification Integration Guide

## Goal

Integrate **sendotp.email** into the BunkLoop Django backend for email OTP verification.

The API key has already been added to the environment under:

```env
otp_email_key=YOUR_EXISTING_KEY
```

> Do **not** rename the environment variable unless the project configuration requires it.
> Do **not** expose the API key to frontend JavaScript, templates, API responses, logs, Git, or Docker images.

---

# 1. Intended Authentication Flow

Implement this flow:

```text
User enters email
        ↓
Frontend calls Django POST /api/auth/send-email-otp/
        ↓
Django validates + normalizes email
        ↓
Django calls sendotp.email POST /v1/send
        ↓
sendotp.email emails OTP
        ↓
Django stores challenge ID temporarily
        ↓
Frontend asks user for OTP
        ↓
Frontend calls POST /api/auth/verify-email-otp/
        ↓
Django calls sendotp.email POST /v1/verify
        ↓
If valid:
    mark email/session/user as verified
        ↓
Continue signup / allow account access
```

The frontend must **never** communicate with sendotp.email directly.

All sendotp.email calls must originate from the Django backend.

---

# 2. sendotp.email API Contract

Base URL:

```text
https://api.sendotp.email
```

## Send OTP

```http
POST /v1/send
```

Headers:

```http
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

Payload:

```json
{
  "email": "student@example.com",
  "purpose": "signup",
  "language": "en"
}
```

Successful response is expected to contain approximately:

```json
{
  "ok": true,
  "id": "otp_...",
  "resent": false,
  "expiresAt": 1700000600
}
```

The returned `id` is the **challenge ID**.

It is required later during verification.

---

## Verify OTP

```http
POST /v1/verify
```

Payload:

```json
{
  "email": "student@example.com",
  "purpose": "signup",
  "id": "otp_...",
  "code": "493021"
}
```

Successful verification:

```json
{
  "valid": true
}
```

Incorrect/expired/etc. OTP may still return HTTP 200 with:

```json
{
  "valid": false,
  "reason": "wrong_code"
}
```

Therefore, do **not** treat HTTP 200 alone as successful OTP verification.

Always check:

```python
response_data.get("valid") is True
```

---

# 3. Install HTTP Client

Prefer `requests` unless the project already standardizes on another HTTP client.

Add:

```bash
pip install requests
```

Add it to the project's dependency file.

For example:

```text
requirements.txt
```

should contain:

```text
requests
```

Do not install a second HTTP library if the project already uses `httpx`, unless there is a good reason.

---

# 4. Load the API Key Through Django Settings

In the relevant Django settings module:

```python
import os

OTP_EMAIL_API_KEY = os.getenv("otp_email_key")
```

Optionally also define:

```python
SENDOTP_BASE_URL = "https://api.sendotp.email"
SENDOTP_PURPOSE_SIGNUP = "signup"
```

At application startup/development, ensure the key exists.

Do not hardcode the actual API key.

Do not write:

```python
OTP_EMAIL_API_KEY = "actual-secret-key"
```

---

# 5. Docker Environment Handling

Because BunkLoop is Dockerized, ensure `otp_email_key` reaches the Django container.

If Docker Compose uses an `.env` file:

```yaml
services:
  web:
    env_file:
      - .env
```

or explicitly:

```yaml
services:
  web:
    environment:
      otp_email_key: ${otp_email_key}
```

Do not write the real key directly inside `docker-compose.yml`.

Make sure `.env` is ignored by Git:

```gitignore
.env
.env.*
!.env.example
```

An `.env.example` may contain:

```env
otp_email_key=
```

but never the actual secret.

---

# 6. Create a Dedicated OTP Service Module

Do not put raw third-party API logic directly inside Django views.

Create something similar to:

```text
accounts/
├── services/
│   ├── __init__.py
│   └── email_otp.py
```

Suggested implementation:

```python
import requests
from django.conf import settings


SEND_URL = f"{settings.SENDOTP_BASE_URL}/v1/send"
VERIFY_URL = f"{settings.SENDOTP_BASE_URL}/v1/verify"

DEFAULT_PURPOSE = "signup"


class OTPServiceError(Exception):
    pass


def _headers():
    if not settings.OTP_EMAIL_API_KEY:
        raise OTPServiceError("OTP email API key is not configured.")

    return {
        "Authorization": f"Bearer {settings.OTP_EMAIL_API_KEY}",
        "Content-Type": "application/json",
    }


def normalize_email(email: str) -> str:
    return email.strip().lower()


def send_email_otp(email: str, purpose: str = DEFAULT_PURPOSE):
    email = normalize_email(email)

    payload = {
        "email": email,
        "purpose": purpose,
        "language": "en",
    }

    try:
        response = requests.post(
            SEND_URL,
            headers=_headers(),
            json=payload,
            timeout=10,
        )
    except requests.RequestException as exc:
        raise OTPServiceError("OTP provider is currently unavailable.") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise OTPServiceError("Invalid response from OTP provider.") from exc

    if response.status_code == 200 and data.get("ok") is True:
        return {
            "id": data.get("id"),
            "resent": data.get("resent", False),
            "expires_at": data.get("expiresAt"),
        }

    # Provider resend cooldown
    if response.status_code == 429 and data.get("error") == "resend_cooldown":
        return {
            "cooldown": True,
            "id": data.get("id"),
            "expires_at": data.get("expiresAt"),
            "retry_after": data.get("retryAfter"),
        }

    # Provider rate limit
    if response.status_code == 429:
        raise OTPServiceError("Too many OTP requests. Please try again later.")

    # Disposable / temporary email
    if (
        response.status_code == 422
        and data.get("error") == "temporary_email_not_allowed"
    ):
        raise OTPServiceError(
            "Temporary or disposable email addresses are not allowed."
        )

    raise OTPServiceError(
        data.get("message") or data.get("error") or "Could not send OTP."
    )


def verify_email_otp(
    email: str,
    challenge_id: str,
    code: str,
    purpose: str = DEFAULT_PURPOSE,
):
    email = normalize_email(email)

    payload = {
        "email": email,
        "purpose": purpose,
        "id": challenge_id,
        "code": str(code).strip(),
    }

    try:
        response = requests.post(
            VERIFY_URL,
            headers=_headers(),
            json=payload,
            timeout=10,
        )
    except requests.RequestException as exc:
        raise OTPServiceError("OTP provider is currently unavailable.") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise OTPServiceError("Invalid response from OTP provider.") from exc

    if response.status_code == 200:
        return {
            "valid": data.get("valid") is True,
            "reason": data.get("reason"),
        }

    raise OTPServiceError(
        data.get("message") or data.get("error") or "Could not verify OTP."
    )
```

Adapt imports/module names to the existing project structure rather than blindly creating duplicate apps.

---

# 7. Do Not Store the OTP Code

The backend should **not** store the six-digit OTP sent to the student.

sendotp.email performs the actual OTP validation.

The application only needs to retain enough state to associate the user's verification attempt with the challenge.

At minimum:

```text
email
challenge_id
purpose
expiry
```

The safest hackathon implementation is to store this state in:

1. Redis — preferred because Redis is already part of BunkLoop.
2. Django cache backed by Redis.
3. Session storage as a fallback.

Do not create unnecessary permanent database rows for every OTP request.

---

# 8. Recommended Redis / Django Cache Strategy

Use Django's cache abstraction if Redis caching is already configured.

Example key:

```text
email_otp:signup:<normalized_email>
```

Example stored value:

```python
{
    "challenge_id": "otp_...",
    "expires_at": 1700000600
}
```

Cache timeout:

```text
10 minutes / 600 seconds
```

Example:

```python
from django.core.cache import cache


def otp_cache_key(email):
    email = email.strip().lower()
    return f"email_otp:signup:{email}"
```

When the send API succeeds:

```python
cache.set(
    otp_cache_key(email),
    {
        "challenge_id": result["id"],
        "expires_at": result["expires_at"],
    },
    timeout=600,
)
```

On successful verification:

```python
cache.delete(otp_cache_key(email))
```

This prevents unnecessary permanent OTP state.

---

# 9. Create Send OTP Endpoint

Recommended route:

```text
POST /api/auth/send-email-otp/
```

Expected request:

```json
{
  "email": "student@example.com"
}
```

The endpoint should:

1. Ensure email is present.
2. Normalize email using `.strip().lower()`.
3. Validate normal email syntax.
4. Apply any BunkLoop-specific university restrictions, if currently enabled.
5. Call `send_email_otp()`.
6. Store returned challenge ID in Redis/cache.
7. Return only safe metadata to frontend.
8. Never return the OTP itself.
9. Never return the API key.
10. Do not unnecessarily return provider internals.

Example Django REST Framework view:

```python
from django.core.cache import cache
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .services.email_otp import (
    send_email_otp,
    OTPServiceError,
)


def otp_cache_key(email):
    return f"email_otp:signup:{email.strip().lower()}"


@api_view(["POST"])
@permission_classes([AllowAny])
def send_otp_view(request):
    email = str(request.data.get("email", "")).strip().lower()

    if not email:
        return Response(
            {"error": "Email is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validate_email(email)
    except ValidationError:
        return Response(
            {"error": "Enter a valid email address."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        result = send_email_otp(email, purpose="signup")
    except OTPServiceError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    challenge_id = result.get("id")

    if challenge_id:
        cache.set(
            otp_cache_key(email),
            {
                "challenge_id": challenge_id,
                "expires_at": result.get("expires_at"),
            },
            timeout=600,
        )

    if result.get("cooldown"):
        return Response(
            {
                "success": True,
                "message": "An OTP was already sent recently.",
                "retry_after": result.get("retry_after"),
            },
            status=status.HTTP_200_OK,
        )

    return Response(
        {
            "success": True,
            "message": "Verification code sent.",
            "expires_at": result.get("expires_at"),
        },
        status=status.HTTP_200_OK,
    )
```

---

# 10. Create Verify OTP Endpoint

Recommended route:

```text
POST /api/auth/verify-email-otp/
```

Expected request:

```json
{
  "email": "student@example.com",
  "code": "493021"
}
```

The frontend should **not need to manage the provider challenge ID**.

Instead, retrieve the challenge ID from Redis/cache using the email.

This reduces client-side state and prevents clients from freely supplying arbitrary challenge IDs.

Example:

```python
from django.core.cache import cache

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .services.email_otp import (
    verify_email_otp,
    OTPServiceError,
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

    cached = cache.get(otp_cache_key(email))

    if not cached:
        return Response(
            {
                "verified": False,
                "error": "OTP expired or no verification request exists."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    challenge_id = cached.get("challenge_id")

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

    if not result["valid"]:
        reason = result.get("reason")

        messages = {
            "wrong_code": "Incorrect verification code.",
            "expired": "Verification code has expired.",
            "locked": "Too many incorrect attempts. Request a new code.",
            "superseded": "This verification code is no longer active.",
        }

        return Response(
            {
                "verified": False,
                "error": messages.get(
                    reason,
                    "Verification failed. Request a new code if necessary.",
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    cache.delete(otp_cache_key(email))

    #
    # IMPORTANT:
    # Mark the email verification state here.
    #
    # Exact implementation depends on the existing signup architecture.
    #

    return Response(
        {
            "verified": True,
            "message": "Email verified successfully.",
        },
        status=status.HTTP_200_OK,
    )
```

Do not assume every possible provider `reason` value is known.

Always include a safe fallback message.

---

# 11. Connect Verification to the Existing User Model

Inspect the current project before modifying models.

If the project already has something like:

```python
is_email_verified
email_verified
email_verified_at
```

use it.

Do not create duplicate fields.

If no verification state exists and accounts are created before OTP verification, consider:

```python
email_verified = models.BooleanField(default=False)
email_verified_at = models.DateTimeField(null=True, blank=True)
```

After successful verification:

```python
from django.utils import timezone

user.email_verified = True
user.email_verified_at = timezone.now()

user.save(
    update_fields=[
        "email_verified",
        "email_verified_at",
    ]
)
```

However, first inspect the signup flow.

If accounts are created **only after OTP validation**, it may be cleaner to avoid creating an unverified user at all.

---

# 12. Preferred BunkLoop Signup Architecture

For this hackathon, prefer:

```text
Step 1
User enters registration details
        ↓
Step 2
Send OTP to email
        ↓
Step 3
Verify OTP
        ↓
Step 4
Create / activate account
        ↓
Step 5
Login
```

Avoid letting completely unverified users freely use marketplace features.

---

# 13. Verification Token / Session State

A potential security problem occurs if the frontend verifies one email and then changes the email before account creation.

Example attack:

```text
verify:
student@university.edu

then signup:
attacker@gmail.com
```

Do not trust a frontend boolean such as:

```json
{
  "email_verified": true
}
```

The backend must maintain verification state.

Recommended options:

## Option A — Server session

After successful OTP verification:

```python
request.session["verified_signup_email"] = email
```

During signup:

```python
verified_email = request.session.get("verified_signup_email")

if verified_email != submitted_email.strip().lower():
    reject_signup()
```

After successful registration:

```python
request.session.pop("verified_signup_email", None)
```

## Option B — Short-lived signed verification token

Generate a Django-signed short-lived token after verification and require it during signup.

For the hackathon, server session state is simpler if sessions already exist.

---

# 14. URL Configuration

Example:

```python
from django.urls import path
from .views import send_otp_view, verify_otp_view

urlpatterns = [
    path(
        "api/auth/send-email-otp/",
        send_otp_view,
        name="send-email-otp",
    ),
    path(
        "api/auth/verify-email-otp/",
        verify_otp_view,
        name="verify-email-otp",
    ),
]
```

Adapt route organization to the current application instead of duplicating an existing `/api/auth/` prefix.

---

# 15. Frontend Integration

The frontend needs two API calls.

## Send

```javascript
await fetch("/api/auth/send-email-otp/", {
    method: "POST",
    headers: {
        "Content-Type": "application/json",
    },
    body: JSON.stringify({
        email: email,
    }),
});
```

After success:

```text
show OTP entry UI
start/restart resend timer
```

---

## Verify

```javascript
await fetch("/api/auth/verify-email-otp/", {
    method: "POST",
    headers: {
        "Content-Type": "application/json",
    },
    body: JSON.stringify({
        email: email,
        code: otp,
    }),
});
```

If:

```json
{
  "verified": true
}
```

continue registration.

Do not call sendotp.email from browser JavaScript.

---

# 16. Resend OTP

The same send endpoint can be used for resend:

```text
POST /api/auth/send-email-otp/
```

sendotp.email keeps the same active code during the live challenge window.

The provider can return:

```text
429 resend_cooldown
```

with:

```json
{
  "retryAfter": 30
}
```

Pass a safe `retry_after` value to the frontend so the resend button can be temporarily disabled.

Frontend example:

```text
Resend code in 30s
```

Do not aggressively retry the provider.

---

# 17. Rate Limiting

Provider-side limits are not enough.

Protect your own endpoints too.

Recommended:

```text
send OTP:
~3-5 requests per email/IP over a short window

verify OTP:
limit repeated attempts
```

If Django REST Framework throttling is already configured, reuse it.

If Redis is already available, application-level rate limiting can use Redis.

Do not spend excessive hackathon time building a complex anti-abuse system, but do not leave the endpoint completely unprotected.

---

# 18. CSRF / Authentication Considerations

OTP endpoints will normally be accessible before login.

If using DRF:

```python
permission_classes = [AllowAny]
```

may be appropriate.

But follow the project's existing authentication architecture.

Do not globally disable CSRF protection merely to make OTP work.

If the frontend and backend use normal Django session authentication, preserve the project's existing CSRF handling.

---

# 19. University Email Restriction

BunkLoop is a campus marketplace.

If the project currently requires university-only emails, perform that validation **before** sending an OTP.

Example concept:

```python
ALLOWED_EMAIL_DOMAINS = {
    "lpu.in",
}
```

Then:

```python
domain = email.rsplit("@", 1)[-1].lower()

if domain not in ALLOWED_EMAIL_DOMAINS:
    return Response(
        {"error": "Please use your university email address."},
        status=400,
    )
```

Do not hardcode a domain without checking the current project's intended university/domain policy.

If the MVP currently allows all valid emails, leave this restriction configurable rather than adding an arbitrary restriction.

---

# 20. Error Handling

Handle at least:

### Invalid email

Return:

```json
{
  "error": "Enter a valid email address."
}
```

### Disposable email

Provider may return HTTP 422:

```text
temporary_email_not_allowed
```

Show:

```text
Temporary or disposable email addresses are not allowed.
```

### Resend cooldown

Provider may return HTTP 429:

```text
resend_cooldown
```

Use its `retryAfter` field when available.

### Rate limiting

Show a generic message:

```text
Too many requests. Please try again later.
```

### Incorrect OTP

Do not expose excessive provider details.

Show:

```text
Incorrect verification code.
```

### Expired challenge

Show:

```text
Verification code expired. Request a new code.
```

### Provider unavailable / timeout

Show:

```text
Email verification is temporarily unavailable. Please try again.
```

Do not show stack traces to the frontend.

---

# 21. Logging

Safe to log:

```text
OTP send attempted
OTP verification succeeded/failed
provider status code
provider reason category
```

Avoid logging:

```text
actual OTP code
API key
Authorization header
full secrets
```

Prefer masking emails where practical.

Example:

```text
r***@example.com
```

---

# 22. Security Checklist

Before considering the feature complete, verify:

- [ ] API key remains backend-only.
- [ ] `otp_email_key` is loaded from environment.
- [ ] `.env` is excluded from Git.
- [ ] Docker receives the env variable securely.
- [ ] Frontend never sees the API key.
- [ ] Frontend never calls `api.sendotp.email` directly.
- [ ] Email is normalized before send and verify.
- [ ] Same stable `purpose` is used for send and verify.
- [ ] Challenge ID from `/v1/send` is retained server-side.
- [ ] Challenge ID is deleted after successful verification.
- [ ] OTP code itself is not stored in BunkLoop's database/cache.
- [ ] HTTP 200 from `/v1/verify` is not automatically treated as valid.
- [ ] Code checks `data["valid"]`.
- [ ] Signup cannot change email after a different address was verified.
- [ ] Verification state is decided server-side.
- [ ] Resend endpoint handles cooldown.
- [ ] Endpoint has basic abuse/rate protection.
- [ ] Provider timeouts are configured.
- [ ] Secrets and OTPs are excluded from logs.

---

# 23. Testing Checklist

## Test 1 — Valid email

1. Enter a real email.
2. Call send endpoint.
3. Confirm email arrives.
4. Enter correct OTP.
5. Verify response contains:

```json
{
  "verified": true
}
```

---

## Test 2 — Incorrect code

Use:

```text
000000
```

or another incorrect value.

Expected:

```text
verified = false
```

Account must remain unverified.

---

## Test 3 — Expired code

Wait until the challenge expires and try verification.

Expected:

```text
verification rejected
```

---

## Test 4 — Resend

Request another OTP during the live window.

Ensure:

- no duplicate challenge confusion occurs,
- backend handles provider resend cooldown,
- frontend displays resend timing sensibly.

---

## Test 5 — Disposable address

Test a known disposable provider.

Expected:

```text
request rejected
```

---

## Test 6 — Missing API key

Temporarily remove:

```env
otp_email_key
```

Expected:

```text
controlled backend error
```

not:

```text
500 traceback exposed to client
```

---

## Test 7 — Docker

Run the complete stack through Docker/Compose.

Inside the Django container, confirm the variable exists without printing its value.

For example:

```bash
python -c "import os; print(bool(os.getenv('otp_email_key')))"
```

Expected:

```text
True
```

Never print the actual secret during demonstrations.

---

## Test 8 — Email swapping attack

1. Verify `student1@example.com`.
2. Attempt signup using `student2@example.com`.

Expected:

```text
registration rejected until student2@example.com is verified
```

---

# 24. Automated Tests

Mock the sendotp.email API.

Do not send real emails for every Django unit test.

Test cases should include:

```text
send success
send cooldown
provider rate limit
disposable email rejection
network timeout
verify success
wrong code
expired code
missing cached challenge
email normalization
email-swapping prevention
```

Suggested approach:

```python
from unittest.mock import patch
```

Mock:

```python
requests.post
```

Do not depend on the live service for the normal automated test suite.

---

# 25. Suggested File Structure

Adapt this to the existing codebase:

```text
accounts/
├── services/
│   ├── __init__.py
│   └── email_otp.py
├── views.py
├── urls.py
├── models.py
└── tests/
    └── test_email_otp.py
```

If the project already separates API views, serializers, services, or authentication modules, integrate there instead.

Do not restructure unrelated areas of the project just for this feature.

---

# 26. Agent Implementation Order

The coding agent should perform work in this order:

### Phase 1 — Inspect

1. Locate Django settings.
2. Locate `.env` loading mechanism.
3. Locate Docker Compose/container configuration.
4. Locate authentication/signup app.
5. Locate user model.
6. Locate current signup/login views and URLs.
7. Check whether DRF is installed.
8. Check whether Redis/Django cache is already configured.
9. Check whether email verification fields already exist.

Do not write duplicate infrastructure before inspection.

---

### Phase 2 — Configuration

1. Load `otp_email_key` in settings.
2. Define sendotp base URL.
3. Ensure the Docker web/Django service receives the variable.
4. Add `requests` only if an equivalent client is not already installed.

---

### Phase 3 — Provider Service

Implement:

```python
send_email_otp()
verify_email_otp()
```

in a dedicated service module.

Include:

```text
timeouts
safe exception handling
email normalization
send cooldown handling
disposable email handling
provider rate limit handling
```

---

### Phase 4 — Temporary Challenge State

Use existing Redis/Django cache.

Store:

```text
email → challenge ID
```

for approximately 10 minutes.

Do not store OTP codes.

---

### Phase 5 — API Views

Implement:

```text
POST /api/auth/send-email-otp/
POST /api/auth/verify-email-otp/
```

or equivalent routes matching the current project's URL style.

---

### Phase 6 — Signup Integration

Ensure:

```text
an email must be verified before registration/activation succeeds
```

and:

```text
verified email == submitted signup email
```

Verification must be enforced server-side.

---

### Phase 7 — Frontend

Connect:

```text
email form
send OTP button
OTP input
verify button
resend timer
error states
success state
```

No API key or provider URL should be required by frontend code.

---

### Phase 8 — Testing

Run:

```bash
python manage.py check
python manage.py test
```

or the project's equivalent test command.

Then manually test through Docker.

---

# 27. Acceptance Criteria

The integration is complete only when all of the following work:

```text
[ ] User submits email.
[ ] Django validates email.
[ ] Django sends request to sendotp.email.
[ ] OTP arrives in inbox.
[ ] Challenge ID is retained server-side.
[ ] User submits OTP.
[ ] Django verifies OTP through sendotp.email.
[ ] Wrong OTP is rejected.
[ ] Correct OTP marks email as verified.
[ ] User cannot substitute a different email after verification.
[ ] Resend works without creating broken state.
[ ] Provider cooldown/rate-limit errors are handled.
[ ] Secret stays out of frontend and Git.
[ ] Feature works inside Docker.
```

---

# 28. Important Instructions to the Coding Agent

**Do not blindly paste this guide.**

Before making changes:

1. Inspect the existing project architecture.
2. Reuse existing authentication, Redis, caching, environment, serializer, URL, and model conventions.
3. Avoid duplicate fields/routes/services.
4. Keep modifications focused on OTP verification.
5. Do not break existing signup/login behavior.
6. Do not expose `otp_email_key`.
7. Never commit `.env`.
8. Never return the OTP code from BunkLoop APIs.
9. Do not weaken CSRF/authentication globally.
10. Preserve Docker compatibility.

After implementation, report:

```text
Files changed
New endpoints
How OTP state is stored
How signup verification is enforced
Any migrations created
Environment/Docker changes
Tests performed
Any remaining issues
```

---

# Final Target Flow

```text
          BunkLoop Frontend
                 │
                 │ email
                 ▼
       POST /send-email-otp/
                 │
                 ▼
          Django Backend
                 │
                 │ Bearer otp_email_key
                 ▼
      api.sendotp.email/v1/send
                 │
                 ▼
           Student Inbox
                 │
              6-digit OTP
                 │
                 ▼
          BunkLoop Frontend
                 │
              email + OTP
                 ▼
      POST /verify-email-otp/
                 │
                 ▼
          Django Backend
                 │
       reads challenge from Redis
                 │
                 ▼
     api.sendotp.email/v1/verify
                 │
           valid = true
                 ▼
        Server marks email
            as verified
                 │
                 ▼
          Signup continues
```

The central rule is:

> **sendotp.email verifies the OTP; BunkLoop verifies that the successfully verified email is the same email being used for the account.**
