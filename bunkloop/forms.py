import re
from urllib.parse import urlparse

import dns.resolver
from django import forms
from django.core.exceptions import ValidationError
from email_validator import EmailNotValidError, validate_email

from .models import Hostel, Item, ItemCategory, ProfileImage, University, User


def validate_student_email(email):
    try:
        validated = validate_email(email, check_deliverability=True)
        normalized_email = validated.email
    except EmailNotValidError:
        raise ValidationError('Please enter a valid email address.')

    domain = normalized_email.split('@')[-1].lower()
    if not domain or '.' not in domain:
        raise ValidationError('Please enter a valid university email domain.')

    denied_domains = {'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com', 'aol.com'}
    if domain in denied_domains:
        raise ValidationError('Please use a valid university or student email address.')

    if not (domain.endswith('.edu') or '.ac.' in domain or 'university' in domain or 'edu.' in domain):
        raise ValidationError('Only university or academic student email domains are allowed.')

    try:
        answers = dns.resolver.resolve(domain, 'MX')
        if not answers:
            raise ValidationError('This email domain could not be verified.')
    except Exception:
        raise ValidationError('This email domain could not be verified. Please use a valid student email.')

    return normalized_email


class UserProfileForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=False)
    university = forms.ModelChoiceField(queryset=University.objects.none(), required=True, empty_label='Choose university')
    hostel = forms.ModelChoiceField(queryset=Hostel.objects.none(), required=False, empty_label='Choose hostel')
    gender = forms.CharField(required=False)
    identity_photo = forms.ImageField(required=True, widget=forms.ClearableFileInput(attrs={'accept': 'image/*', 'capture': 'environment'}))
    profile_image = forms.ModelChoiceField(
        queryset=ProfileImage.objects.all(),
        required=False,
        empty_label='Choose a profile photo',
    )

    class Meta:
        model = User
        fields = [
            'full_name',
            'registration_id',
            'university',
            'profile_image',
            'contact_number',
            'student_type',
            'hostel',
            'email',
            'gender',
            'password',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['university'].queryset = University.objects.order_by('name')
        self.fields['hostel'].queryset = Hostel.objects.select_related('university').order_by('university__name', 'name')
        self.fields['hostel'].required = False
        self.fields['profile_image'].required = False

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if not email:
            raise ValidationError('Email is required.')
        return validate_student_email(email)

    def clean_gender(self):
        gender = (self.cleaned_data.get('gender') or '').strip()
        mapping = {
            'Female': 'female',
            'Male': 'male',
            'Non-binary': 'non_binary',
            'Prefer not to say': 'prefer_not_to_say',
            'Other': 'other',
            'female': 'female',
            'male': 'male',
            'non_binary': 'non_binary',
            'prefer_not_to_say': 'prefer_not_to_say',
            'other': 'other',
        }
        return mapping.get(gender, gender)

    def clean_student_type(self):
        student_type = (self.cleaned_data.get('student_type') or '').strip()
        mapping = {
            'Hosteler': 'hosteler',
            'Day scholar': 'day_scholar',
            'PG': 'pg',
            'day_scholar': 'day_scholar',
            'hosteler': 'hosteler',
            'pg': 'pg',
        }
        return mapping.get(student_type, student_type)

    def clean(self):
        cleaned_data = super().clean()
        student_type = cleaned_data.get('student_type')
        hostel_value = cleaned_data.get('hostel')
        hostel_name = hostel_value.name if hasattr(hostel_value, 'name') else (hostel_value or '').strip()

        if student_type == 'hosteler' and not hostel_name:
            raise ValidationError({'hostel': 'Hostel is required for hosteler students.'})

        password = cleaned_data.get('password')
        confirm_password = self.cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match.')

        if cleaned_data.get('identity_photo') is None:
            self.add_error('identity_photo', 'A live camera photo is required for registration.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        university = self.cleaned_data.get('university')
        hostel = self.cleaned_data.get('hostel')
        gender = self.cleaned_data.get('gender')

        user.university = university
        user.hostel = hostel
        user.gender = gender or ''
        user.identity_photo = self.cleaned_data.get('identity_photo')
        user.email_verified = True
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class ItemForm(forms.ModelForm):
    title = forms.CharField()
    description = forms.CharField(required=False, widget=forms.Textarea)
    category = forms.ModelChoiceField(queryset=ItemCategory.objects.none(), required=True, empty_label='Choose a category')
    price = forms.DecimalField(min_value=0)
    listing_type = forms.CharField()
    condition = forms.CharField()

    class Meta:
        model = Item
        fields = ['title', 'description', 'category', 'price', 'listing_type', 'condition']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ItemCategory.objects.order_by('name')

    def clean_listing_type(self):
        listing_type = (self.cleaned_data.get('listing_type') or '').strip()
        mapping = {
            'sell': 'selling',
            'selling': 'selling',
            'rent': 'renting',
            'renting': 'renting',
        }
        return mapping.get(listing_type, listing_type)

    def clean_condition(self):
        condition = (self.cleaned_data.get('condition') or '').strip()
        mapping = {
            'New': 'new',
            'Like New': 'like_new',
            'Good': 'good',
            'Fair': 'fair',
            'Needs Repair': 'needs_repair',
            'new': 'new',
            'like_new': 'like_new',
            'good': 'good',
            'fair': 'fair',
            'needs_repair': 'needs_repair',
        }
        return mapping.get(condition, condition)

    def save(self, commit=True, **kwargs):
        item = super().save(commit=False)
        item.category = self.cleaned_data.get('category')
        item.listing_type = self.cleaned_data.get('listing_type') or item.listing_type
        item.condition = self.cleaned_data.get('condition') or item.condition
        if commit:
            item.save()
        return item
