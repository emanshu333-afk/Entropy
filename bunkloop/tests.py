from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from io import BytesIO

from bunkloop.models import Hostel, Item, ItemCategory, ItemImage, ProfileImage, University, User


def create_test_image():
    """Create a simple valid test image."""
    image = Image.new('RGB', (100, 100), color='red')
    image_io = BytesIO()
    image.save(image_io, format='JPEG')
    image_io.seek(0)
    return image_io


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
                    create_test_image().getvalue(),
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
    def test_signup_rejects_non_student_email_domain(self):
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
                'email': 'aarav@gmail.com',
                'gender': 'male',
                'password': 'StrongPass123',
                'confirm_password': 'StrongPass123',
                'agree_tnd': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='aarav@gmail.com').exists())

    def test_signup_redirects_to_otp_verification_for_valid_student_email(self):
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
                'agree_tnd': 'on',
                'identity_photo': SimpleUploadedFile(
                    'selfie.jpg',
                    create_test_image().getvalue(),
                    content_type='image/jpeg',
                ),
            },
            follow=True,
        )

        self.assertTrue(response.redirect_chain)
        self.assertTrue(User.objects.filter(email='aarav@thapar.edu').exists() is False)
        self.assertIn('verify', str(response.redirect_chain[0][0]))


class MessagingFlowTest(TestCase):
    def setUp(self):
        self.uni = University.objects.create(name='Msg Uni')
        self.hostel = Hostel.objects.create(name='Msg Hostel', university=self.uni)
        self.cat = ItemCategory.objects.create(name='Gadgets')
        self.seller = User.objects.create_user(
            username='seller_msg', email='seller_msg@thapar.edu', password='TestPass123',
            full_name='Seller Msg', registration_id='SELLMSG01', university=self.uni, gender='male'
        )
        self.buyer = User.objects.create_user(
            username='buyer_msg', email='buyer_msg@thapar.edu', password='TestPass123',
            full_name='Buyer Msg', registration_id='BUYMSG01', university=self.uni, gender='female'
        )
        self.item = Item.objects.create(
            title='Msg Item', description='Test', registration_id=self.seller, category=self.cat,
            price=1000, listing_type='selling', condition='good'
        )

    def test_buyer_can_start_conversation_and_send_message(self):
        self.client.post(reverse('bunkloop:login'), {'identifier': 'buyer_msg@thapar.edu', 'password': 'TestPass123'})
        resp = self.client.post(reverse('bunkloop:start_conversation', args=[self.item.pk]), {'body': 'Hi, available?'}, follow=True)
        self.assertEqual(resp.status_code, 200)
        from bunkloop.models import Conversation
        conv = Conversation.objects.filter(item=self.item, buyer=self.buyer).first()
        self.assertIsNotNone(conv)
        self.assertEqual(conv.seller, self.seller)
        self.assertEqual(conv.messages.count(), 1)
        # send second message via detail
        resp2 = self.client.post(reverse('bunkloop:conversation_detail', args=[conv.pk]), {'body': 'Second'}, follow=True)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(conv.messages.count(), 2)

    def test_conversation_is_isolated_to_participants(self):
        from bunkloop.models import Conversation
        conv = Conversation.objects.create(item=self.item, buyer=self.buyer, seller=self.seller)
        # third user cannot access
        third = User.objects.create_user(username='third', email='third@thapar.edu', password='TestPass123', full_name='Third', registration_id='THIRD01', university=self.uni)
        self.client.post(reverse('bunkloop:login'), {'identifier': 'third@thapar.edu', 'password': 'TestPass123'})
        resp = self.client.get(reverse('bunkloop:conversation_detail', args=[conv.pk]))
        # should redirect to conversation_list with error
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/messages/', resp.url)


class OrderFlowTest(TestCase):
    def setUp(self):
        self.uni = University.objects.create(name='Order Uni')
        self.cat = ItemCategory.objects.create(name='OrderCat')
        self.seller = User.objects.create_user(username='seller_ord', email='seller_ord@thapar.edu', password='TestPass123', full_name='Seller Ord', registration_id='SELLORD01', university=self.uni)
        self.buyer = User.objects.create_user(username='buyer_ord', email='buyer_ord@thapar.edu', password='TestPass123', full_name='Buyer Ord', registration_id='BUYORD01', university=self.uni)
        self.item = Item.objects.create(title='Order Item', description='Desc', registration_id=self.seller, category=self.cat, price=2500, listing_type='selling', condition='like_new')

    def test_checkout_creates_order_and_seller_can_confirm(self):
        self.client.post(reverse('bunkloop:login'), {'identifier': 'buyer_ord@thapar.edu', 'password': 'TestPass123'})
        resp = self.client.post(reverse('bunkloop:order_create', args=[self.item.pk]), follow=True)
        self.assertEqual(resp.status_code, 200)
        from bunkloop.models import Order
        order = Order.objects.filter(item=self.item, buyer=self.buyer).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.status, 'paid')
        self.assertEqual(order.payment_status, 'succeeded')
        # seller confirms
        self.client.post(reverse('bunkloop:login'), {'identifier': 'seller_ord@thapar.edu', 'password': 'TestPass123'})
        resp2 = self.client.post(reverse('bunkloop:order_update_status', args=[order.pk]), {'status': 'confirmed'}, follow=True)
        order.refresh_from_db()
        self.assertEqual(order.status, 'confirmed')
        # shipped
        self.client.post(reverse('bunkloop:order_update_status', args=[order.pk]), {'status': 'shipped'}, follow=True)
        order.refresh_from_db()
        self.assertEqual(order.status, 'shipped')
        # delivered
        self.client.post(reverse('bunkloop:order_update_status', args=[order.pk]), {'status': 'delivered'}, follow=True)
        order.refresh_from_db()
        self.assertEqual(order.status, 'delivered')
        # buyer completes
        self.client.post(reverse('bunkloop:login'), {'identifier': 'buyer_ord@thapar.edu', 'password': 'TestPass123'})
        self.client.post(reverse('bunkloop:order_update_status', args=[order.pk]), {'status': 'completed'}, follow=True)
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')

    def test_health_endpoint(self):
        resp = self.client.get('/health/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'ok')
