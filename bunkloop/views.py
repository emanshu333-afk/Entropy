from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ItemForm, UserProfileForm
from .models import Hostel, Item, ItemCategory, ItemImage, ProfileImage, University, User


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
            user = form.save(commit=False)
            user.username = user.email.split('@')[0] + '-' + user.registration_id
            user.set_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, 'Profile created successfully. Please log in.')
            return redirect('bunkloop:login')
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
