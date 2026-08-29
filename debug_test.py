import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'entropy.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from bunkloop.models import University, Hostel, ProfileImage, User
from django.core.files.uploadedfile import SimpleUploadedFile

# Create test data
university, _ = University.objects.get_or_create(name='Thapar university Test')
hostel, _ = Hostel.objects.get_or_create(name='A Block Test', university=university)
avatar, _ = ProfileImage.objects.get_or_create(name='Male avatar Test', defaults={'pfp_type': 'male', 'image_url': 'https://example.com/male.png'})

# Make the request
client = Client()
response = client.post(
    reverse('bunkloop:signup'),
    {
        'full_name': 'Test User',
        'registration_id': 'T-TEST-001',
        'university': str(university.pk),
        'profile_image': str(avatar.pk),
        'contact_number': '+91 9876543210',
        'student_type': 'hosteler',
        'hostel': str(hostel.pk),
        'email': 'testuser@thapar.edu',
        'gender': 'male',
        'password': 'StrongPass123',
        'confirm_password': 'StrongPass123',
        'identity_photo': SimpleUploadedFile('selfie.jpg', b'fake-image-bytes', content_type='image/jpeg'),
    },
    follow=True,
)

print('Status:', response.status_code)
print('URL:', response.url if hasattr(response, 'url') else 'N/A')
print('Content-Type:', response.get('Content-Type', 'N/A'))
print('Redirect chain:', response.redirect_chain if hasattr(response, 'redirect_chain') else 'N/A')

# Check if form context exists
if hasattr(response, 'context') and response.context:
    print('Context keys:', list(response.context.keys()) if response.context else [])
    if 'form' in response.context:
        form = response.context['form']
        print('\nForm is_bound:', form.is_bound)
        print('Form is_valid:', form.is_valid())
        if not form.is_valid():
            print('Form errors:')
            for field, errors in form.errors.items():
                print(f'  {field}: {errors}')
    else:
        print('No form in context')
else:
    print('No context found')
    # Try to extract errors from HTML
    if 'error' in response.content.decode('utf-8', errors='ignore').lower():
        print('\nResponse contains "error" - form likely failed')
        # Print first 500 chars of response
        content = response.content.decode('utf-8', errors='ignore')
        error_idx = content.lower().find('error')
        if error_idx > -1:
            print('Error section:', content[max(0, error_idx-100):min(len(content), error_idx+200)])

# Check if user was created
user_exists = User.objects.filter(email='testuser@thapar.edu').exists()
print(f'\nUser created: {user_exists}')
