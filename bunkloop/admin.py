from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Hostel,
    Item,
    ItemCategory,
    ItemImage,
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


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


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
