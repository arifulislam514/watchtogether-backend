# rooms/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Room, RoomMember, Message


class RoomMemberInline(admin.TabularInline):
    model        = RoomMember
    extra        = 0
    readonly_fields = ('id', 'user', 'is_ready', 'joined_at')
    can_delete   = True


class MessageInline(admin.TabularInline):
    model        = Message
    extra        = 0
    readonly_fields = ('id', 'sender', 'text', 'sent_at')
    can_delete   = True
    ordering     = ('-sent_at',)
    max_num      = 50   # cap to avoid very large inline tables


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display    = ('name', 'host', 'video', 'member_count_display', 'is_active', 'created_at')
    list_filter     = ('is_active',)
    search_fields   = ('name', 'host__email')
    ordering        = ('-created_at',)
    readonly_fields = ('id', 'invite_token', 'created_at')
    inlines         = [RoomMemberInline, MessageInline]

    fieldsets = (
        ('Room',        {'fields': ('id', 'name', 'host', 'video')}),
        ('Access',      {'fields': ('password', 'invite_token', 'max_members', 'is_active')}),
        ('Timestamps',  {'fields': ('created_at',)}),
    )

    actions = ['deactivate_rooms', 'activate_rooms']

    def member_count_display(self, obj):
        count = obj.members.count()
        colour = '#ef4444' if obj.is_full else '#10b981'
        return format_html(
            '<span style="color:{};">{}/{}</span>',
            colour, count, obj.max_members
        )
    member_count_display.short_description = 'Members'

    @admin.action(description='Deactivate selected rooms')
    def deactivate_rooms(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} room(s) deactivated.')

    @admin.action(description='Activate selected rooms')
    def activate_rooms(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} room(s) activated.')


@admin.register(RoomMember)
class RoomMemberAdmin(admin.ModelAdmin):
    list_display  = ('user', 'room', 'is_ready', 'joined_at')
    list_filter   = ('is_ready',)
    search_fields = ('user__email', 'room__name')
    ordering      = ('-joined_at',)
    readonly_fields = ('id', 'joined_at')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display  = ('sender', 'room', 'short_text', 'sent_at')
    search_fields = ('sender__email', 'room__name', 'text')
    ordering      = ('-sent_at',)
    readonly_fields = ('id', 'sent_at')

    def short_text(self, obj):
        return obj.text[:80] + ('…' if len(obj.text) > 80 else '')
    short_text.short_description = 'Message'
