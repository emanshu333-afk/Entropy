from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from bunkloop.models import Hostel, Item, ItemCategory, ItemImage, ProfileImage, University, User


class UserProfileFieldTest(TestCase):
    def test_student_profile_fields_and_relationships(self):
        university = University.objects.create(name='Sample University')
        hostel = Hostel.objects.create(name='A-Block', university=university)
        avatar = ProfileImage.objects.create(
            name='Default avatar',
            image_url='https://example.com/images/default.png',
        )

        user = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='TestPass123',
            full_name='Alice Johnson',
            registration_id='REG-1001',
            university=university,
            profile_image=avatar,
            contact_number='+91 9876543210',
            student_type='hosteler',
            hostel=hostel,
            gender='female',
        )

        self.assertEqual(user.full_name, 'Alice Johnson')
        self.assertEqual(user.registration_id, 'REG-1001')
        self.assertEqual(user.university.name, 'Sample University')
        self.assertEqual(user.profile_image.image_url, 'https://example.com/images/default.png')
        self.assertEqual(user.student_type, 'hosteler')
        self.assertEqual(user.hostel.name, 'A-Block')
        self.assertEqual(user.gender, 'female')


class ItemListingFieldTest(TestCase):
    def test_item_listing_fields_and_image_limit(self):
        university = University.objects.create(name='Alpha University')
        user = User.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='TestPass123',
            full_name='Bob Smith',
            registration_id='REG-2002',
            university=university,
            contact_number='+91 9999999999',
            gender='male',
        )
        category = ItemCategory.objects.create(name='Books')

        item = Item.objects.create(
            registration_id=user,
            category=category,
            price=2500,
            listing_type='selling',
            condition='like_new',
        )

        for i in range(4):
            ItemImage.objects.create(
                item=item,
                image=SimpleUploadedFile(
                    f'item-{i}.jpg',
                    b'fake-image-bytes',
                    content_type='image/jpeg',
                ),
            )

        self.assertEqual(item.registration_id.registration_id, 'REG-2002')
        self.assertEqual(item.category.name, 'Books')
        self.assertEqual(item.listing_type, 'selling')
        self.assertEqual(item.condition, 'like_new')
        self.assertEqual(item.images.count(), 4)


class AppRouteRegressionTest(TestCase):
    def test_required_routes_exist(self):
        self.assertEqual(reverse('bunkloop:home'), '/')
        self.assertEqual(reverse('bunkloop:login'), '/login/')
        self.assertEqual(reverse('bunkloop:signup'), '/signup/')
        self.assertEqual(reverse('bunkloop:profile'), '/profile/')


class SignupFlowTest(TestCase):
    def test_signup_creates_user_when_form_is_valid(self):
        university = University.objects.create(name='Thapar university')
        hostel = Hostel.objects.create(name='A Block', university=university)
        avatar = ProfileImage.objects.create(
            name='Male avatar',
            pfp_type='male',
            image_url='https://example.com/male.png',
        )

        response = self.client.post(
            reverse('bunkloop:signup'),
            {
                'full_name': 'Aarav Sharma',
                'registration_id': 'T-1001',
                'university': str(university.pk),
                'profile_image': str(avatar.pk),
                'contact_number': '+91 9876543210',
                'student_type': 'hosteler',
                'hostel': str(hostel.pk),
                'email': 'aarav@thapar.edu',
                'gender': 'male',
                'password': 'StrongPass123',
                'confirm_password': 'StrongPass123',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email='aarav@thapar.edu').exists())

        user = User.objects.get(email='aarav@thapar.edu')
        self.assertEqual(user.university, university)
        self.assertEqual(user.hostel, hostel)
        self.assertTrue(user.check_password('StrongPass123'))
