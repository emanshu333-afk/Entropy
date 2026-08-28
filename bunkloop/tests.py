from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

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
            listing_type='sell',
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
        self.assertEqual(item.listing_type, 'sell')
        self.assertEqual(item.condition, 'like_new')
        self.assertEqual(item.images.count(), 4)
