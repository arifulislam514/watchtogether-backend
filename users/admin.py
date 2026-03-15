# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, FriendRequest


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display   = ('email', 'name', 'is_active', 'is_staff', 'created_at')
    list_filter    = ('is_active', 'is_staff')
    search_fields  = ('email', 'name')
    ordering       = ('-created_at',)
    actions        = ['ban_users', 'unban_users']

    fieldsets = (
        (None,          {'fields': ('email', 'password')}),
        ('Personal',    {'fields': ('name', 'avatar')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields':  ('email', 'name', 'password1', 'password2'),
        }),
    )

    @admin.action(description='Ban selected users')
    def ban_users(self, request, queryset):
        queryset.exclude(is_superuser=True).update(is_active=False)

    @admin.action(description='Unban selected users')
    def unban_users(self, request, queryset):
        queryset.update(is_active=True)


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display  = ('sender', 'receiver', 'status', 'created_at')
    list_filter   = ('status',)
    search_fields = ('sender__email', 'receiver__email')
    
