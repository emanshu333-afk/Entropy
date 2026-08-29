from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class University(models.Model):
    """Predefined university list that can be managed dynamically."""

    name = models.CharField(max_length=200, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ProfileImage(models.Model):
    """Predefined profile pictures uploaded by an administrator."""

    PFP_TYPE_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('non_binary', 'Non-binary'),
    ]

    name = models.CharField(max_length=100, unique=True)
    pfp_type = models.CharField(max_length=20, choices=PFP_TYPE_CHOICES, default='non_binary')
    image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True, default='')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Hostel(models.Model):
    """Hostel choices tied to a specific university."""

    name = models.CharField(max_length=120)
    university = models.ForeignKey(University, on_delete=models.CASCADE, related_name='hostels')

    class Meta:
        unique_together = ('university', 'name')
        ordering = ['university__name', 'name']

    def __str__(self):
        return f'{self.name} ({self.university})'


class User(AbstractUser):
    """Student profile model used for the PG share application."""

    STUDENT_TYPE_CHOICES = [
        ('day_scholar', 'Day scholar'),
        ('pg', 'PG'),
        ('hosteler', 'Hosteler'),
    ]

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('non_binary', 'Non-binary'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say'),
    ]

    full_name = models.CharField(max_length=200)
    registration_id = models.CharField(max_length=50, unique=True, db_index=True)
    university = models.ForeignKey(University, on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    profile_image = models.ForeignKey(ProfileImage, on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    contact_number = models.CharField(max_length=20, blank=True, default='')
    student_type = models.CharField(max_length=20, choices=STUDENT_TYPE_CHOICES, default='day_scholar')
    hostel = models.ForeignKey(Hostel, on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    email = models.EmailField(unique=True)
    gender = models.CharField(max_length=30, choices=GENDER_CHOICES, blank=True, default='')

    REQUIRED_FIELDS = ['email', 'full_name', 'registration_id']

    def clean(self):
        super().clean()
        if self.student_type == 'hosteler' and not self.hostel:
            raise ValidationError({'hostel': 'Hostel is required for hosteler students.'})

    def __str__(self):
        return self.full_name


class ItemCategory(models.Model):
    """Predefined categories from which an item can be listed."""

    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Item(models.Model):
    """Item listing created by a registered student."""

    ITEM_CONDITION_CHOICES = [
        ('new', 'New'),
        ('like_new', 'Like New'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('needs_repair', 'Needs Repair'),
    ]

    LISTING_TYPE_CHOICES = [
        ('selling', 'Selling'),
        ('renting', 'Renting'),
    ]

    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, default='')
    registration_id = models.ForeignKey(User, to_field='registration_id', on_delete=models.CASCADE, related_name='items')
    category = models.ForeignKey(ItemCategory, on_delete=models.PROTECT, related_name='items')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    listing_type = models.CharField(max_length=10, choices=LISTING_TYPE_CHOICES, default='selling')
    condition = models.CharField(max_length=20, choices=ITEM_CONDITION_CHOICES, default='good')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} - {self.registration_id}'


class ItemImage(models.Model):
    """Up to four images for each item listing. Images are captured live from the camera."""

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='item_images/')

    class Meta:
        ordering = ['id']

    def clean(self):
        super().clean()
        if self.item_id and self.item.images.count() >= 4:
            raise ValidationError('You can upload a maximum of 4 images per item.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'Image for {self.item}'
