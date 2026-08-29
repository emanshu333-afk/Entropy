import random

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from django.conf import settings

from .forms import ItemForm, UserProfileForm
from .models import Conversation, Hostel, Item, ItemCategory, ItemImage, Message, Order, ProfileImage, University, User

OTP_STORE = {}


def require_login(view_func):
    def wrapped(request, *args, **kwargs):
        if not request.session.get('user_registration_id'):
            return redirect('bunkloop:login')
        return view_func(request, *args, **kwargs)
    return wrapped


def login_view(request):
    # Redirect authenticated users away from auth pages on GET; allow POST to switch accounts
    if request.method == 'GET' and request.session.get('user_registration_id'):
        return redirect('bunkloop:home')
    if request.method == 'POST':
        # If already logged in and trying to log in as different user, clear session first
        if request.session.get('user_registration_id'):
            from django.contrib.auth import logout as auth_logout
            auth_logout(request)
            request.session.flush()
        identifier = request.POST.get('identifier', '').strip()
        password = request.POST.get('password', '')
        user_record = User.objects.filter(email__iexact=identifier).first()
        if user_record is None:
            user_record = User.objects.filter(registration_id=identifier).first()
        user = authenticate(
            request,
            username=user_record.username if user_record else identifier,
            password=password,
        )
        if user is not None:
            login(request, user)
            request.session['user_registration_id'] = user.registration_id
            request.session['user_email'] = user.email
            return redirect('bunkloop:home')
        messages.error(request, 'Invalid email or password.')
    return render(request, 'bunkloop/login.html')


def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('bunkloop:login')


def custom_404(request, exception):
    return render(request, 'bunkloop/404.html', {'exception': exception}, status=404)


def health_check(request):
    """Simple health endpoint for container probes."""
    from django.http import JsonResponse
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    status = 200 if db_ok else 500
    return JsonResponse({'status': 'ok' if db_ok else 'error', 'db': db_ok}, status=status)


@require_login
def profile(request):
    user = User.objects.filter(registration_id=request.session.get('user_registration_id')).select_related('university', 'hostel').first()
    if not user:
        request.session.flush()
        return redirect('bunkloop:login')
    return render(request, 'bunkloop/profile.html', {'user': user})


@require_login
def home(request):
    user_registration_id = request.session.get('user_registration_id')
    user = User.objects.filter(registration_id=user_registration_id).select_related('university').first()
    if not user or not user.university:
        messages.warning(request, 'Complete your profile to view campus listings.')
        return redirect('bunkloop:signup')

    categories = ItemCategory.objects.order_by('name')
    listings = Item.objects.filter(registration_id__university=user.university).select_related('category', 'registration_id').prefetch_related('images').order_by('-created_at')

    # Frontend-visible filters: search and category
    q = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()
    active_category = None
    if category_id:
        try:
            active_category = ItemCategory.objects.get(pk=int(category_id))
            listings = listings.filter(category=active_category)
        except (ValueError, ItemCategory.DoesNotExist):
            active_category = None
    if q:
        listings = listings.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(category__name__icontains=q))

    # For nav badge: unread messages and pending orders
    unread_count = Message.objects.filter(conversation__in=Conversation.objects.filter(Q(buyer=user) | Q(seller=user)), is_read=False).exclude(sender=user).count()
    pending_orders = Order.objects.filter(Q(buyer=user, status__in=['paid','confirmed','shipped','delivered']) | Q(seller=user, status__in=['paid','confirmed','shipped'])).count()

    return render(request, 'bunkloop/home.html', {
        'listings': listings,
        'user': user,
        'categories': categories,
        'q': q,
        'active_category': active_category,
        'unread_count': unread_count,
        'pending_orders': pending_orders,
    })


def signup(request):
    # Redirect authenticated users away from signup if they already have a complete profile
    # If they have no university, allow them to view signup to complete profile (breaks home→signup loop)
    reg_id = request.session.get('user_registration_id')
    if reg_id:
        try:
            _cur = User.objects.filter(registration_id=reg_id).select_related('university').first()
            has_uni = _cur and _cur.university_id
        except Exception:
            has_uni = False
        if has_uni:
            # Already has profile → signup not needed, go home
            return redirect('bunkloop:home')
        # No university → allow to stay on signup to complete profile (don't redirect)
        # For POST while logged in with no uni, also allow (will create new user after flush if needed)
        if request.method == 'POST':
            from django.contrib.auth import logout as auth_logout
            auth_logout(request)
            request.session.flush()
    universities = University.objects.order_by('name')
    hostels = Hostel.objects.select_related('university').order_by('university__name', 'name')
    profile_image_options = {
        'male': ProfileImage.objects.filter(pfp_type='male').order_by('name'),
        'female': ProfileImage.objects.filter(pfp_type='female').order_by('name'),
        'non_binary': ProfileImage.objects.filter(pfp_type='non_binary').order_by('name'),
    }

    if request.method == 'POST':
        # TnD agreement is required (new)
        if not request.POST.get('agree_tnd'):
            # Create a form to show error, but also add a message
            form = UserProfileForm(request.POST, request.FILES)
            # Trigger validation to populate errors
            form.is_valid()
            form.add_error(None, 'You must agree to the Terms & Conditions to create an account.')
            # Fall through to render with error - need to create context
            universities = University.objects.order_by('name')
            hostels = Hostel.objects.select_related('university').order_by('university__name', 'name')
            profile_image_options = {
                'male': ProfileImage.objects.filter(pfp_type='male').order_by('name'),
                'female': ProfileImage.objects.filter(pfp_type='female').order_by('name'),
                'non_binary': ProfileImage.objects.filter(pfp_type='non_binary').order_by('name'),
            }
            return render(
                request,
                'bunkloop/signup.html',
                {
                    'form': form,
                    'universities': universities,
                    'hostels': hostels,
                    'profile_image_options': profile_image_options,
                },
            )
        form = UserProfileForm(request.POST, request.FILES)
        if form.is_valid():
            email = form.cleaned_data['email']
            # Enforce session-based verification (guide §13): if email already verified via /api/auth/verify-email-otp/, create account directly
            verified_email = request.session.get('verified_signup_email')
            if verified_email and verified_email.strip().lower() == email.strip().lower():
                # Email already verified via sendotp.email API — create user directly (skip OTP)
                # Reuse same identity photo handling but bypass OTP generation
                identity_file = form.cleaned_data.get('identity_photo')
                identity_bytes = None
                identity_name = None
                identity_content_type = None
                if identity_file:
                    try:
                        identity_file.seek(0)
                    except Exception:
                        pass
                    identity_bytes = identity_file.read()
                    identity_name = getattr(identity_file, 'name', 'identity.jpg')
                    identity_content_type = getattr(identity_file, 'content_type', 'image/jpeg')
                from django.core.files.uploadedfile import SimpleUploadedFile as _SUF
                identity_upload = None
                if identity_bytes:
                    identity_upload = _SUF(identity_name or 'identity.jpg', identity_bytes, content_type=identity_content_type or 'image/jpeg')
                # Direct user creation (guide §12: create after OTP)
                form_data = form.cleaned_data
                user = User(
                    username=form_data['email'].split('@')[0] + '-' + form_data['registration_id'],
                    email=form_data['email'],
                    full_name=form_data['full_name'],
                    registration_id=form_data['registration_id'],
                    university=form_data['university'],
                    profile_image=form_data['profile_image'],
                    contact_number=form_data.get('contact_number', ''),
                    student_type=form_data.get('student_type', 'day_scholar'),
                    hostel=form_data.get('hostel'),
                    gender=form_data.get('gender', ''),
                    identity_photo=identity_upload,
                    is_active=True,
                    email_verified=True,
                )
                user.set_password(form_data['password'])
                user.save()
                # Clear verification session (guide §13)
                request.session.pop('verified_signup_email', None)
                request.session.pop('verified_signup_at', None)
                # Also clear any pending OTP cache
                try:
                    from django.core.cache import cache as _cache
                    from .email_otp import otp_cache_key as _otp_key
                    _cache.delete(_otp_key(email))
                except Exception:
                    pass
                messages.success(request, 'Profile created successfully. Please log in.')
                return redirect('bunkloop:login')

            # Not yet verified — try sendotp.email first (guide §9), fallback to local OTP
            identity_file = form.cleaned_data.get('identity_photo')
            identity_bytes = None
            identity_name = None
            identity_content_type = None
            if identity_file:
                try:
                    identity_file.seek(0)
                except Exception:
                    pass
                identity_bytes = identity_file.read()
                identity_name = getattr(identity_file, 'name', 'identity.jpg')
                identity_content_type = getattr(identity_file, 'content_type', 'image/jpeg')
            form_data_copy = {k: v for k, v in form.cleaned_data.items() if k != 'identity_photo'}
            ttl = getattr(settings, 'OTP_TTL_SECONDS', 600)

            # Try sendotp.email service (guide §6) — if API key configured, use it
            _used_sendotp = False
            try:
                from .email_otp import send_email_otp, otp_cache_key
                from django.core.cache import cache as _cache
                # This will raise OTPServiceError if key not configured — then fallback to local
                result = send_email_otp(email, purpose=getattr(settings, 'SENDOTP_PURPOSE_SIGNUP', 'signup'))
                # Store challenge_id in cache (guide §8) — never store OTP code
                if result.get('id'):
                    _cache.set(
                        otp_cache_key(email),
                        {
                            "challenge_id": result.get('id'),
                            "expires_at": result.get('expires_at'),
                            "form_data": form_data_copy,
                            "identity_photo_bytes": identity_bytes,
                            "identity_photo_name": identity_name,
                            "identity_photo_content_type": identity_content_type,
                        },
                        timeout=ttl,
                    )
                    _used_sendotp = True
                    # Also keep OTP_STORE fallback for verify view compatibility (but without OTP)
                    OTP_STORE[email] = {
                        'otp': None,  # No OTP stored when using sendotp.email
                        'expires_at': timezone.now().timestamp() + ttl,
                        'form_data': form_data_copy,
                        'identity_photo_bytes': identity_bytes,
                        'identity_photo_name': identity_name,
                        'identity_photo_content_type': identity_content_type,
                        'challenge_id': result.get('id'),
                        'via_sendotp': True,
                    }
                    if result.get('cooldown'):
                        messages.info(request, f"An OTP was already sent recently. Retry after {result.get('retry_after')}s.")
                    else:
                        messages.success(request, 'Verification code sent to your student email. Please enter the OTP to continue.')
                    request.session['pending_email'] = email
                    request.session['pending_registration'] = {'email': email}
                    return redirect('bunkloop:verify_email')
            except Exception as _e:
                # Fallback to local OTP if sendotp.email not configured or failed (dev/test)
                if not _used_sendotp:
                    import logging as _log
                    _log.getLogger(__name__).info(f"sendotp.email not used for {email}: {_e} — falling back to local OTP")

            # Fallback: local OTP generation (dev/test without API key)
            otp_len = getattr(settings, 'OTP_LENGTH', 6)
            _otp_start = 10 ** (otp_len - 1)
            _otp_end = (10 ** otp_len) - 1
            otp = str(random.randint(_otp_start, _otp_end))
            ttl = getattr(settings, 'OTP_TTL_SECONDS', 600)
            OTP_STORE[email] = {
                'otp': otp,
                'expires_at': timezone.now().timestamp() + ttl,
                'form_data': form_data_copy,
                'identity_photo_bytes': identity_bytes,
                'identity_photo_name': identity_name,
                'identity_photo_content_type': identity_content_type,
            }
            ttl_min = ttl // 60
            send_mail(
                subject='Bunkloop email verification',
                message=f'Your OTP is {otp}. It is valid for {ttl_min} minutes.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )
            if settings.DEBUG:
                from django.utils.timezone import localtime
                expiry = localtime(timezone.now() + timezone.timedelta(seconds=ttl))
                print(f"[BunkLoop OTP FALLBACK] {email} -> {otp} (valid {ttl_min}m, expires {expiry:%d %b %Y %I:%M %p IST})")
                import logging
                logging.getLogger(__name__).info(f"Fallback OTP for {email} expires at {expiry:%Y-%m-%d %H:%M:%S IST}")
            request.session['pending_email'] = email
            request.session['pending_registration'] = {'email': email}
            messages.success(request, 'Verification code sent to your student email. Please enter the OTP to continue.')
            return redirect('bunkloop:verify_email')
    else:
        form = UserProfileForm()
    return render(
        request,
        'bunkloop/signup.html',
        {
            'form': form,
            'universities': universities,
            'hostels': hostels,
            'profile_image_options': profile_image_options,
        },
    )


def verify_email(request):
    pending_email = request.session.get('pending_email')
    if not pending_email:
        return redirect('bunkloop:signup')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()
        stored = OTP_STORE.get(pending_email)
        # Also try cache for sendotp.email challenge (guide §8)
        _cached_challenge = None
        try:
            from django.core.cache import cache as _cache
            from .email_otp import otp_cache_key as _otp_key
            _cached_challenge = _cache.get(_otp_key(pending_email))
        except Exception:
            _cached_challenge = None

        if not stored and not _cached_challenge:
            messages.error(request, 'Verification code expired. Please try again.')
            return redirect('bunkloop:signup')

        # Use stored from OTP_STORE if exists, else from cache (which has form_data for sendotp case)
        # For sendotp case, stored may have via_sendotp
        is_via_sendotp = False
        challenge_id = None
        if stored and stored.get('via_sendotp'):
            is_via_sendotp = True
            challenge_id = stored.get('challenge_id') or (_cached_challenge.get('challenge_id') if _cached_challenge else None)
        elif _cached_challenge and _cached_challenge.get('challenge_id'):
            # Fallback: cache has challenge but OTP_STORE not marked via_sendotp (edge)
            is_via_sendotp = True
            challenge_id = _cached_challenge.get('challenge_id')
            # Ensure stored has form_data for user creation
            if not stored:
                stored = _cached_challenge

        if is_via_sendotp and challenge_id:
            # Verify via sendotp.email service (guide §10) — never trust OTP directly
            try:
                from .email_otp import verify_email_otp, OTPServiceError
                result = verify_email_otp(email=pending_email, challenge_id=challenge_id, code=entered_otp, purpose=getattr(settings, 'SENDOTP_PURPOSE_SIGNUP', 'signup'))
                if not result.get('valid'):
                    reason = result.get('reason')
                    msg_map = {
                        "wrong_code": "Incorrect verification code.",
                        "expired": "Verification code has expired. Please request a new code.",
                        "locked": "Too many incorrect attempts. Request a new code.",
                        "superseded": "This code is no longer active. Please request a new code.",
                    }
                    messages.error(request, msg_map.get(reason, "Verification failed. Request a new code if necessary."))
                    return render(request, 'bunkloop/verify_email.html', {'email': pending_email})
                # Valid — mark session as verified (guide §13)
                request.session['verified_signup_email'] = pending_email.strip().lower()
                from django.utils import timezone as _tz
                request.session['verified_signup_at'] = _tz.now().isoformat()
            except Exception as e:
                # Handle OTPServiceError and others
                from .email_otp import OTPServiceError as _OTPErr
                if isinstance(e, _OTPErr):
                    messages.error(request, str(e))
                else:
                    messages.error(request, "Email verification is temporarily unavailable. Please try again.")
                return render(request, 'bunkloop/verify_email.html', {'email': pending_email})
        else:
            # Fallback local OTP (dev/test without API key) — original logic
            if not stored:
                messages.error(request, 'Verification code expired. Please try again.')
                return redirect('bunkloop:signup')
            if float(timezone.now().timestamp()) > stored['expires_at']:
                messages.error(request, 'Verification code expired. Please request a new one.')
                return redirect('bunkloop:signup')
            if entered_otp != stored['otp']:
                messages.error(request, 'Invalid verification code. Please try again.')
                return render(request, 'bunkloop/verify_email.html', {'email': pending_email})
            # Also mark as verified for session enforcement
            request.session['verified_signup_email'] = pending_email.strip().lower()
            from django.utils import timezone as _tz2
            request.session['verified_signup_at'] = _tz2.now().isoformat()

        # Create the user now that OTP is verified
        form_data = stored['form_data']
        identity_bytes = stored.get('identity_photo_bytes')
        identity_name = stored.get('identity_photo_name') or 'identity.jpg'
        identity_content_type = stored.get('identity_photo_content_type') or 'image/jpeg'
        identity_upload = None
        if identity_bytes:
            identity_upload = SimpleUploadedFile(identity_name, identity_bytes, content_type=identity_content_type)
        user = User(
            username=form_data['email'].split('@')[0] + '-' + form_data['registration_id'],
            email=form_data['email'],
            full_name=form_data['full_name'],
            registration_id=form_data['registration_id'],
            university=form_data['university'],
            profile_image=form_data['profile_image'],
            contact_number=form_data.get('contact_number', ''),
            student_type=form_data.get('student_type', 'day_scholar'),
            hostel=form_data.get('hostel'),
            gender=form_data.get('gender', ''),
            identity_photo=identity_upload,
            is_active=True,
            email_verified=True,
        )
        user.set_password(form_data['password'])
        user.save()
        OTP_STORE.pop(pending_email, None)
        # Also clear cache challenge (guide §8)
        try:
            from django.core.cache import cache as _cache2
            from .email_otp import otp_cache_key as _otp_key2
            _cache2.delete(_otp_key2(pending_email))
        except Exception:
            pass
        request.session.pop('pending_email', None)
        request.session.pop('pending_registration', None)
        messages.success(request, 'Profile created successfully. Please log in.')
        return redirect('bunkloop:login')

    return render(request, 'bunkloop/verify_email.html', {'email': pending_email})


@require_login
def my_items(request):
    registration_id = request.session.get('user_registration_id') or request.GET.get('registration_id')
    listings = Item.objects.select_related('category', 'registration_id').filter(registration_id__registration_id=registration_id).order_by('-created_at') if registration_id else Item.objects.none()
    # Enrich listings with conversation/order counts for frontend visibility
    for item in listings:
        item.conv_count = Conversation.objects.filter(item=item).count()
        item.order_count = Order.objects.filter(item=item).count()
        item.pending_order = Order.objects.filter(item=item, status__in=['paid','confirmed','shipped']).first()
    return render(request, 'bunkloop/my_items.html', {'listings': listings, 'registration_id': registration_id})


@require_login
def item_create(request):
    categories = ItemCategory.objects.order_by('name')
    current_user = User.objects.filter(registration_id=request.session.get('user_registration_id')).first()
    if not current_user:
        request.session.flush()
        return redirect('bunkloop:login')

    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES)
        if form.is_valid():
            files = request.FILES.getlist('photos')
            if not files:
                form.add_error(None, 'Add at least one photo before publishing.')
                return render(request, 'bunkloop/item_form.html', {'form': form, 'categories': categories})
            if len(files) > 4:
                form.add_error(None, 'You can upload a maximum of 4 photos.')
                return render(request, 'bunkloop/item_form.html', {'form': form, 'categories': categories})

            item = form.save(commit=False)
            item.registration_id = current_user
            with transaction.atomic():
                item.save()
                for photo in files:
                    ItemImage.objects.create(item=item, image=photo)

            messages.success(request, 'Item listed successfully.')
            return redirect('bunkloop:my_items')
    else:
        form = ItemForm()
    return render(request, 'bunkloop/item_form.html', {'form': form, 'categories': categories})


@require_login
def item_detail(request, pk):
    current_user = User.objects.filter(
        registration_id=request.session.get('user_registration_id'),
    ).select_related('university').first()
    item = get_object_or_404(
        Item.objects.select_related('category', 'registration_id').prefetch_related('images'),
        pk=pk,
        registration_id__university=current_user.university,
    )
    # Check if buyer already has a conversation for this item
    existing_conversation = None
    if current_user and current_user.pk != item.registration_id.pk:
        existing_conversation = Conversation.objects.filter(item=item, buyer=current_user).first()
    # Check if buyer has an order for this item
    existing_order = None
    if current_user:
        existing_order = Order.objects.filter(item=item, buyer=current_user).order_by('-created_at').first()
    return render(request, 'bunkloop/item_detail.html', {'item': item, 'existing_conversation': existing_conversation, 'existing_order': existing_order, 'current_user': current_user})


@require_login
def item_delete(request, pk):
    user = _get_current_user(request)
    if not user:
        request.session.flush()
        return redirect('bunkloop:login')
    item = get_object_or_404(
        Item.objects.select_related('registration_id'),
        pk=pk,
        registration_id=user,
    )
    if request.method == 'POST':
        title = item.title
        # Prevent deletion if orders exist (PROTECT) — show friendly message
        if item.orders.exists():
            messages.error(request, f'Cannot remove "{title}" — it has orders. Cancel orders first or contact support.')
            return redirect('bunkloop:my_items')
        try:
            with transaction.atomic():
                # Delete related images first (cascade) then item
                item.images.all().delete()
                item.delete()
            messages.success(request, f'"{title}" removed from your listings.')
        except Exception as e:
            messages.error(request, f'Could not remove "{title}": {e}')
        return redirect('bunkloop:my_items')
    return render(request, 'bunkloop/item_confirm_delete.html', {'item': item})


def university_list(request):
    # Public listing — shows backend University → domains mapping
    universities = University.objects.prefetch_related('hostels').order_by('name')
    # Annotate student count for visibility
    from django.db.models import Count
    universities = universities.annotate(student_count=Count('students'))
    return render(request, 'bunkloop/universities.html', {'universities': universities})


def terms_view(request):
    """Terms and Conditions page (TnD) — per user request."""
    return render(request, 'bunkloop/terms.html')


def _get_current_user(request):
    reg_id = request.session.get('user_registration_id')
    if not reg_id:
        return None
    return User.objects.filter(registration_id=reg_id).select_related('university').first()


@require_login
def conversation_list(request):
    user = _get_current_user(request)
    if not user:
        request.session.flush()
        return redirect('bunkloop:login')
    from .services import get_user_conversations, get_unread_count
    conversations = get_user_conversations(user)
    # Annotate unread count and last_message using service (plan §18)
    for conv in conversations:
        conv.unread_count = get_unread_count(conv, user)
        conv.last_message = conv.messages.filter(deleted_at__isnull=True).order_by('-created_at').first()
    return render(request, 'bunkloop/conversations.html', {'conversations': conversations, 'current_user': user})


@require_login
def conversation_detail(request, pk):
    user = _get_current_user(request)
    if not user:
        request.session.flush()
        return redirect('bunkloop:login')
    # Support both integer pk and UUID (plan §35)
    try:
        conversation = Conversation.objects.select_related('item', 'buyer', 'seller', 'university', 'listing').get(pk=pk)
    except (ValueError, Conversation.DoesNotExist):
        try:
            import uuid as _uuid
            _uid = _uuid.UUID(str(pk))
            conversation = get_object_or_404(Conversation.objects.select_related('item', 'buyer', 'seller', 'university', 'listing'), uuid=_uid)
        except Exception:
            conversation = get_object_or_404(Conversation.objects.select_related('item', 'buyer', 'seller', 'university', 'listing'), pk=pk)
    # Security: membership check (plan §13) + university isolation (§6)
    from .services import ensure_conversation_member, mark_conversation_read, get_conversation_messages, create_message
    try:
        ensure_conversation_member(conversation, user)
    except Exception:
        messages.error(request, 'You do not have access to this conversation.')
        return redirect('bunkloop:conversation_list')
    if conversation.university_id and user.university_id and conversation.university_id != user.university_id:
        messages.error(request, 'Conversation not in your university.')
        return redirect('bunkloop:conversation_list')
    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        if body:
            try:
                create_message(conversation=conversation, sender=user, content=body)
            except Exception as e:
                messages.error(request, str(e))
        return redirect('bunkloop:conversation_detail', pk=conversation.pk)
    # Mark as read via service (updates last_read_message + is_read fallback)
    try:
        mark_conversation_read(conversation, user)
    except Exception:
        pass
    # Paginated history (plan §10): default 50, support ?before=<id>
    before_id = request.GET.get('before')
    try:
        limit = int(request.GET.get('limit', '50'))
        limit = max(1, min(limit, 100))
    except Exception:
        limit = 50
    chat_messages = get_conversation_messages(conversation, limit=limit, before_id=before_id)
    return render(request, 'bunkloop/conversation_detail.html', {
        'conversation': conversation,
        'chat_messages': chat_messages,
        'current_user': user,
    })


@require_login
def start_conversation(request, pk):
    user = _get_current_user(request)
    if not user:
        request.session.flush()
        return redirect('bunkloop:login')
    item = get_object_or_404(Item.objects.select_related('registration_id'), pk=pk)
    seller = item.registration_id
    if seller.pk == user.pk:
        messages.error(request, 'You cannot message yourself.')
        return redirect('bunkloop:item_detail', pk=item.pk)
    # Enforce university scope
    if user.university_id and seller.university_id and user.university_id != seller.university_id:
        messages.error(request, 'You can only contact sellers from your university.')
        return redirect('bunkloop:item_detail', pk=item.pk)
    # Use service to ensure university + membership + atomic
    from .services import get_or_create_listing_conversation
    conversation, created = get_or_create_listing_conversation(
        buyer=user,
        seller=seller,
        item=item,
    )
    # Ensure membership rows exist (service creates them, but verify)
    from .models import ConversationMember
    for participant in (user, seller):
        ConversationMember.objects.get_or_create(conversation=conversation, user=participant)
    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        if body:
            # Use service for validation + save
            from .services import create_message
            try:
                create_message(conversation=conversation, sender=user, content=body)
                conversation.save()  # touch updated_at
                messages.success(request, 'Message sent.')
            except Exception as e:
                messages.error(request, str(e))
            return redirect('bunkloop:conversation_detail', pk=conversation.pk)
    # If GET, redirect to conversation detail (with optional prefill)
    return redirect('bunkloop:conversation_detail', pk=conversation.pk)


@require_login
def order_create(request, pk):
    user = _get_current_user(request)
    if not user:
        request.session.flush()
        return redirect('bunkloop:login')
    item = get_object_or_404(Item.objects.select_related('registration_id'), pk=pk)
    seller = item.registration_id
    if seller.pk == user.pk:
        messages.error(request, 'You cannot order your own item.')
        return redirect('bunkloop:item_detail', pk=item.pk)
    if request.method == 'POST':
        # Simple checkout: create order with pending payment, then mock payment success
        with transaction.atomic():
            order = Order.objects.create(
                item=item,
                buyer=user,
                seller=seller,
                amount=item.price,
                listing_type=item.listing_type,
                status='pending',
                payment_status='pending',
                provider='mock',
            )
            # Mock payment gateway: instantly succeed for demo (in production integrate Razorpay/Stripe)
            order.payment_status = 'succeeded'
            order.payment_reference = f'MOCK-{order.pk}-{random.randint(100000,999999)}'
            order.status = 'paid'
            order.save()
        messages.success(request, f'Order #{order.pk} placed successfully. Payment succeeded.')
        return redirect('bunkloop:order_detail', pk=order.pk)
    return render(request, 'bunkloop/order_confirm.html', {'item': item, 'current_user': user})


@require_login
def order_list(request):
    user = _get_current_user(request)
    if not user:
        request.session.flush()
        return redirect('bunkloop:login')
    buyer_orders = Order.objects.filter(buyer=user).select_related('item', 'seller').order_by('-created_at')
    seller_orders = Order.objects.filter(seller=user).select_related('item', 'buyer').order_by('-created_at')
    return render(request, 'bunkloop/orders.html', {
        'buyer_orders': buyer_orders,
        'seller_orders': seller_orders,
        'current_user': user,
    })


@require_login
def order_detail(request, pk):
    user = _get_current_user(request)
    if not user:
        request.session.flush()
        return redirect('bunkloop:login')
    order = get_object_or_404(Order.objects.select_related('item', 'buyer', 'seller'), pk=pk)
    if user.pk not in (order.buyer_id, order.seller_id):
        messages.error(request, 'You do not have access to this order.')
        return redirect('bunkloop:order_list')
    return render(request, 'bunkloop/order_detail.html', {'order': order, 'current_user': user})


@require_login
def order_update_status(request, pk):
    user = _get_current_user(request)
    if not user:
        request.session.flush()
        return redirect('bunkloop:login')
    order = get_object_or_404(Order.objects.select_related('item', 'buyer', 'seller'), pk=pk)
    if request.method != 'POST':
        return redirect('bunkloop:order_detail', pk=order.pk)
    new_status = request.POST.get('status', '').strip()
    # Define allowed transitions
    seller_allowed = {
        'paid': ['confirmed', 'cancelled'],
        'confirmed': ['shipped', 'cancelled'],
        'shipped': ['delivered'],
    }
    buyer_allowed = {
        'delivered': ['completed'],
        'pending': ['cancelled'],
        'paid': ['cancelled'],
    }
    allowed = []
    if user.pk == order.seller_id:
        allowed = seller_allowed.get(order.status, [])
    elif user.pk == order.buyer_id:
        allowed = buyer_allowed.get(order.status, []) + (['cancelled'] if order.status in ['pending','paid','confirmed'] else [])
        # Buyers can cancel pending/paid before seller confirms
        if order.status == 'pending' and user.pk == order.buyer_id:
            allowed = ['cancelled']
    if new_status not in allowed:
        messages.error(request, f'Cannot change status from {order.status} to {new_status}.')
        return redirect('bunkloop:order_detail', pk=order.pk)
    order.status = new_status
    if new_status == 'cancelled':
        order.payment_status = 'cancelled'
    order.save()
    messages.success(request, f'Order status updated to {new_status}.')
    return redirect('bunkloop:order_detail', pk=order.pk)
