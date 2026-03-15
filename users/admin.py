# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, FriendRequest


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display    = ('email', 'name', 'avatar_preview', 'is_active', 'is_staff', 'created_at')
    list_filter     = ('is_active', 'is_staff', 'is_superuser')
    search_fields   = ('email', 'name')
    ordering        = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'avatar_preview')

    fieldsets = (
        ('Account',     {'fields': ('id', 'email', 'password')}),
        ('Profile',     {'fields': ('name', 'avatar', 'avatar_preview')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Timestamps',  {'fields': ('created_at',)}),
    )

    # Used when creating a user from the admin
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields':  ('email', 'name', 'password1', 'password2', 'is_staff', 'is_superuser'),
        }),
    )

    # BaseUserAdmin expects username_field — override to use email
    list_display_links = ('email',)

    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html('<img src="{}" width="36" height="36" style="border-radius:50%;object-fit:cover;">', obj.avatar.url)
        return '—'
    avatar_preview.short_description = 'Avatar'


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display  = ('sender', 'receiver', 'status', 'created_at')
    list_filter   = ('status',)
    search_fields = ('sender__email', 'receiver__email')
    ordering      = ('-created_at',)
    readonly_fields = ('id', 'created_at')

    actions = ['accept_requests', 'decline_requests']

    @admin.action(description='Accept selected friend requests')
    def accept_requests(self, request, queryset):
        updated = queryset.update(status='accepted')
        self.message_user(request, f'{updated} request(s) accepted.')

    @admin.action(description='Decline selected friend requests')
    def decline_requests(self, request, queryset):
        updated = queryset.update(status='declined')
        self.message_user(request, f'{updated} request(s) declined.')
