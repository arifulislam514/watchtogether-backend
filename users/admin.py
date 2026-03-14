# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, FriendRequest


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display   = ('email', 'name', 'is_staff', 'created_at')
    list_filter    = ('is_staff', 'is_active')
    search_fields  = ('email', 'name')
    ordering       = ('-created_at',)

    fieldsets = (
        (None,           {'fields': ('email', 'password')}),
        ('Personal',     {'fields': ('name', 'avatar')}),
        ('Permissions',  {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'password1', 'password2'),
        }),
    )


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display  = ('sender', 'receiver', 'status', 'created_at')
    list_filter   = ('status',)
    search_fields = ('sender__email', 'receiver__email')