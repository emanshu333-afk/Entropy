from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


admin.site.site_header = 'BunkLoop administration'
admin.site.site_title = 'BunkLoop admin'
admin.site.index_title = 'Welcome to BunkLoop'
admin.site.register(User, UserAdmin)
