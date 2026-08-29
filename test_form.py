import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'entropy.settings')
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from bunkloop.models import University, Hostel, ProfileImage
from bunkloop.forms import UserProfileForm

# Create test data
university, _ = University.objects.get_or_create(name='Test Uni for Form')
hostel, _ = Hostel.objects.get_or_create(name='Test Hostel', university=university)
avatar, _ = ProfileImage.objects.get_or_create(name='Test Avatar', defaults={'pfp_type': 'male', 'image_url': 'https://example.com/male.png'})

# Create form data
form_data = {
    'full_name': 'Form Test User',
    'registration_id': 'FORM-TEST-001',
    'university': str(university.pk),
    'profile_image': str(avatar.pk),
    'contact_number': '+91 9876543210',
    'student_type': 'hosteler',
    'hostel': str(hostel.pk),
    'email': 'formtest@thapar.edu',
    'gender': 'male',
    'password': 'StrongPass123',
    'confirm_password': 'StrongPass123',
}

files_data = {
    'identity_photo': SimpleUploadedFile('selfie.jpg', b'fake-image-bytes', content_type='image/jpeg'),
}

# Create the form
form = UserProfileForm(data=form_data, files=files_data)

print('Form is_bound:', form.is_bound)
print('Form is_valid:', form.is_valid())

if not form.is_valid():
    print('\nForm errors:')
    for field, errors in form.errors.items():
        print(f'  {field}:')
        for error in errors:
            print(f'    - {error}')
else:
    print('\nForm is valid! Fields look good.')
