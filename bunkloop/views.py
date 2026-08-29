import random

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ItemForm, UserProfileForm
from .models import Hostel, Item, ItemCategory, ItemImage, ProfileImage, University, User

OTP_STORE = {}


def require_login(view_func):
    def wrapped(request, *args, **kwargs):
        if not request.session.get('user_registration_id'):
            return redirect('bunkloop:login')
        return view_func(request, *args, **kwargs)
    return wrapped


def login_view(request):
    if request.method == 'POST':
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
    listings = Item.objects.filter(registration_id__university=user.university).select_related('category', 'registration_id').order_by('-created_at')
    return render(request, 'bunkloop/home.html', {'listings': listings, 'user': user, 'categories': categories})


def signup(request):
    universities = University.objects.order_by('name')
    hostels = Hostel.objects.select_related('university').order_by('university__name', 'name')
    profile_image_options = {
        'male': ProfileImage.objects.filter(pfp_type='male').order_by('name'),
        'female': ProfileImage.objects.filter(pfp_type='female').order_by('name'),
        'non_binary': ProfileImage.objects.filter(pfp_type='non_binary').order_by('name'),
    }

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES)
        if form.is_valid():
            email = form.cleaned_data['email']
            otp = str(random.randint(100000, 999999))
            # Store form data in session temporarily - don't create user yet
            OTP_STORE[email] = {'otp': otp, 'expires_at': timezone.now().timestamp() + 600, 'form_data': form.cleaned_data, 'user_files': {'identity_photo': form.files['identity_photo'] if 'identity_photo' in form.files else None}}
            send_mail(
                subject='Bunkloop email verification',
                message=f'Your OTP is {otp}. It is valid for 10 minutes.',
                from_email='noreply@bunkloop.local',
                recipient_list=[email],
                fail_silently=True,
            )
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
        if not stored:
            messages.error(request, 'Verification code expired. Please try again.')
            return redirect('bunkloop:signup')
        if float(timezone.now().timestamp()) > stored['expires_at']:
            messages.error(request, 'Verification code expired. Please request a new one.')
            return redirect('bunkloop:signup')
        if entered_otp != stored['otp']:
            messages.error(request, 'Invalid verification code. Please try again.')
            return render(request, 'bunkloop/verify_email.html', {'email': pending_email})

        # Create the user now that OTP is verified
        form_data = stored['form_data']
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
            identity_photo=form_data.get('identity_photo'),
            is_active=True,
            email_verified=True,
        )
        user.set_password(form_data['password'])
        user.save()
        OTP_STORE.pop(pending_email, None)
        request.session.pop('pending_email', None)
        request.session.pop('pending_registration', None)
        messages.success(request, 'Profile created successfully. Please log in.')
        return redirect('bunkloop:login')

    return render(request, 'bunkloop/verify_email.html', {'email': pending_email})


@require_login
def my_items(request):
    registration_id = request.session.get('user_registration_id') or request.GET.get('registration_id')
    listings = Item.objects.select_related('category', 'registration_id').filter(registration_id__registration_id=registration_id).order_by('-created_at') if registration_id else Item.objects.none()
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
    return render(request, 'bunkloop/item_detail.html', {'item': item})
