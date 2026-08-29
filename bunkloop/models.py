import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class University(models.Model):
    """Predefined university list that can be managed dynamically.
    Each university now stores a list of allowed email domains for verification.
    """

    name = models.CharField(max_length=200, unique=True)
    domains = models.JSONField(
        default=list,
        blank=True,
        help_text='List of allowed email domains for this university, e.g. ["thapar.edu", "thapar.ac.in"]. Leave empty to allow any academic domain (fallback to .edu/.ac. check).'
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        # Normalize domains to lowercase, strip, deduplicate
        if self.domains:
            if not isinstance(self.domains, list):
                raise ValidationError({'domains': 'Domains must be a list of domain strings.'})
            cleaned = []
            for d in self.domains:
                if not isinstance(d, str):
                    raise ValidationError({'domains': f'Domain {d!r} must be a string.'})
                d = d.strip().lower()
                if not d:
                    continue
                # Basic domain validation: must contain dot, no @, no spaces
                if '@' in d or ' ' in d or '.' not in d:
                    raise ValidationError({'domains': f'Invalid domain: {d}'})
                if d not in cleaned:
                    cleaned.append(d)
            self.domains = cleaned

    def get_domains_display(self):
        """Human readable comma-separated domains."""
        return ', '.join(self.domains) if self.domains else '— (any .edu/.ac.)'

    def is_domain_allowed(self, domain: str) -> bool:
        """Check if a domain belongs to this university's allowed list.
        Empty list means fallback to generic academic check is used elsewhere.
        """
        if not self.domains:
            return False
        domain = domain.strip().lower()
        for d in self.domains:
            # Exact or subdomain match: e.g., thapar.edu matches mail.thapar.edu
            if domain == d or domain.endswith('.' + d):
                return True
        return False


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
    identity_photo = models.ImageField(upload_to='identity_photos/', blank=True, null=True)
    email_verified = models.BooleanField(default=False)

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

    title = models.CharField(max_length=150, default='Untitled item')
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


class Conversation(models.Model):
    """Private conversation between buyer and seller for a specific listing.
    Extended to match Docker-aware plan: includes university, listing alias, and membership via ConversationMember.
    Keeps legacy buyer/seller fields for backward compatibility during migration.
    """

    # Keep legacy integer PK for backward compat; also expose UUID for new API (non-unique for migration safety, uniqueness enforced at app layer)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, blank=True, null=True)

    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='conversations',
        null=True,
        blank=True,
    )

    # Plan calls this "listing"; our Item is the listing. Keep 'item' for compat, add 'listing' alias.
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='conversations')
    listing = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='listing_conversations',
    )

    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buyer_conversations')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seller_conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('item', 'buyer')
        ordering = ['-updated_at']

    def __str__(self):
        return f'Chat: {self.buyer.registration_id} ↔ {self.seller.registration_id} on {self.item.title}'

    def get_participant_ids(self):
        return {self.buyer_id, self.seller_id}

    def save(self, *args, **kwargs):
        # Auto-fill university and listing from item/seller if not set
        if self.item_id and not self.listing_id:
            self.listing = self.item
        if self.item_id and not self.university_id:
            # Prefer seller's university, fallback to buyer's
            try:
                seller_uni = self.seller.university if self.seller_id else None
                if seller_uni:
                    self.university = seller_uni
                elif self.buyer_id and self.buyer.university_id:
                    self.university = self.buyer.university
                elif self.item.registration_id.university_id:
                    self.university = self.item.registration_id.university
            except Exception:
                pass
        super().save(*args, **kwargs)


class ConversationMember(models.Model):
    """Membership table for scalable auth and read receipts (plan §5)."""

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversation_memberships',
    )
    last_read_message = models.ForeignKey(
        'Message',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    muted = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['conversation', 'user'], name='unique_conversation_member')
        ]

    def __str__(self):
        return f'Member {self.user} in {self.conversation_id}'


class Message(models.Model):
    """Persistent message in a conversation. Extended per plan with message_type, media_url, indexes, soft-delete."""

    class MessageType(models.TextChoices):
        TEXT = 'text', 'Text'
        IMAGE = 'image', 'Image'
        SYSTEM = 'system', 'System'

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    # Keep legacy 'body' for compat; new 'content' is canonical per plan
    body = models.TextField(blank=True, default='')
    content = models.TextField(blank=True, default='')
    message_type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.TEXT)
    media_url = models.URLField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', '-created_at']),
            models.Index(fields=['sender', '-created_at']),
        ]

    def save(self, *args, **kwargs):
        # Sync body/content for compat
        if self.content and not self.body:
            self.body = self.content
        if self.body and not self.content:
            self.content = self.body
        super().save(*args, **kwargs)

    def __str__(self):
        txt = self.content or self.body
        return f'Msg {self.pk} from {self.sender.registration_id} at {self.created_at:%Y-%m-%d %H:%M}: {txt[:20]}'


class Order(models.Model):
    """Order/checkout record tied to an item purchase or rental."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='orders')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buyer_orders')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seller_orders')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    listing_type = models.CharField(max_length=10, choices=Item.LISTING_TYPE_CHOICES, default='selling')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_reference = models.CharField(max_length=200, blank=True, default='')
    provider = models.CharField(max_length=50, blank=True, default='mock')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Order {self.pk} - {self.item.title} ({self.status})'
