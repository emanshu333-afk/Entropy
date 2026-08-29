from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Conversation,
    ConversationMember,
    Hostel,
    Item,
    ItemCategory,
    ItemImage,
    Message,
    Order,
    ProfileImage,
    University,
    User,
)


admin.site.site_header = 'BunkLoop administration'
admin.site.site_title = 'BunkLoop admin'
admin.site.index_title = 'Welcome to BunkLoop'


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'username',
        'full_name',
        'email',
        'registration_id',
        'university',
        'student_type',
    )
    search_fields = ('username', 'full_name', 'email', 'registration_id')
    list_filter = ('student_type', 'university', 'gender')


class UniversityAdminForm(forms.ModelForm):
    # Friendlier comma-separated input; still stores as JSON list
    domains_text = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. thapar.edu, thapar.ac.in'}),
        help_text='Comma-separated allowed email domains for this university. Leave empty to allow any academic domain (fallback to .edu/.ac. check).',
        label='Domains (comma-separated)'
    )

    class Meta:
        model = University
        fields = ['name', 'domains_text']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate text field from JSON list
        if self.instance and self.instance.pk and self.instance.domains:
            self.fields['domains_text'].initial = ', '.join(self.instance.domains)

    def clean_domains_text(self):
        raw = self.cleaned_data.get('domains_text', '')
        if not raw.strip():
            return []
        parts = [p.strip().lower() for p in raw.split(',')]
        cleaned = []
        for d in parts:
            if not d:
                continue
            if '@' in d or ' ' in d or '.' not in d:
                raise forms.ValidationError(f'Invalid domain: {d}')
            if d not in cleaned:
                cleaned.append(d)
        return cleaned

    def save(self, commit=True):
        self.instance.domains = self.cleaned_data.get('domains_text', [])
        # Also run model clean for normalization
        self.instance.full_clean()
        return super().save(commit=commit)


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    form = UniversityAdminForm
    list_display = ('name', 'get_domains_display')
    search_fields = ('name',)
    list_filter = ()

    def get_domains_display(self, obj):
        return obj.get_domains_display()
    get_domains_display.short_description = 'Allowed domains'


@admin.register(ProfileImage)
class ProfileImageAdmin(admin.ModelAdmin):
    list_display = ('name', 'pfp_type', 'image')
    search_fields = ('name',)
    list_filter = ('pfp_type',)


@admin.register(Hostel)
class HostelAdmin(admin.ModelAdmin):
    list_display = ('name', 'university')
    search_fields = ('name', 'university__name')
    list_filter = ('university',)


@admin.register(ItemCategory)
class ItemCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'registration_id', 'category', 'price', 'listing_type', 'condition', 'created_at')
    search_fields = ('title', 'description', 'registration_id__registration_id')
    list_filter = ('category', 'listing_type', 'condition', 'created_at')


@admin.register(ItemImage)
class ItemImageAdmin(admin.ModelAdmin):
    list_display = ('item', 'image')
    search_fields = ('item__title',)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'uuid', 'university', 'item', 'buyer', 'seller', 'updated_at')
    search_fields = ('item__title', 'buyer__registration_id', 'seller__registration_id', 'uuid')
    list_filter = ('university', 'created_at')
    readonly_fields = ('uuid',)


@admin.register(ConversationMember)
class ConversationMemberAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'user', 'muted', 'joined_at')
    search_fields = ('conversation__id', 'user__registration_id')
    list_filter = ('muted',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'message_type', 'created_at', 'is_read', 'deleted_at')
    search_fields = ('body', 'content', 'sender__registration_id')
    list_filter = ('message_type', 'is_read', 'created_at')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'item', 'buyer', 'seller', 'amount', 'status', 'payment_status', 'created_at')
    search_fields = ('item__title', 'buyer__registration_id', 'seller__registration_id')
    list_filter = ('status', 'payment_status', 'listing_type')
