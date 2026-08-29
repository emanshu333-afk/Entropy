import os
import django

os.chdir('c:/Users/aarti/OneDrive/Desktop/PG sharing/entropy/Entropy_temp')
django.setup()

from bunkloop.forms import UserProfileForm
from bunkloop.models import User, University, Hostel, ProfileImage

university = University.objects.create(name='Unique Uni 9701')
hostel = Hostel.objects.create(name='A Block 9701', university=university)
profile = ProfileImage.objects.create(name='male-9701', pfp_type='male', image_url='https://example.com/p.png')

data = {
    'full_name': 'Tester 9701',
    'registration_id': 'REG-9701',
    'university': str(university.pk),
    'profile_image': str(profile.pk),
    'contact_number': '999',
    'student_type': 'hosteler',
    'hostel': str(hostel.pk),
    'email': 'tester9701@example.com',
    'gender': 'male',
    'password': 'StrongPass123',
    'confirm_password': 'StrongPass123',
}

form = UserProfileForm(data)
print('is_valid=', form.is_valid())
print(form.errors.as_json())
if form.is_valid():
    user = form.save(commit=False)
    user.username = user.email.split('@')[0] + '-' + user.registration_id
    user.set_password(form.cleaned_data['password'])
    user.save()
    print('saved=', user.pk, user.email, User.objects.filter(email='tester9701@example.com').count())
