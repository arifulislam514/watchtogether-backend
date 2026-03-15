# rooms/admin.py
from django.contrib import admin
from .models import Room, RoomMember, Message


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display    = ('name', 'host', 'member_count', 'is_active', 'created_at')
    list_filter     = ('is_active',)
    search_fields   = ('name', 'host__email')
    readonly_fields = ('id', 'invite_token', 'created_at')
    actions         = ['close_rooms']

    @admin.display(description='Members')
    def member_count(self, obj):
        return obj.members.count()

    @admin.action(description='Force close selected rooms')
    def close_rooms(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(RoomMember)
class RoomMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'room', 'is_ready', 'joined_at')
    list_filter  = ('is_ready',)
    search_fields= ('user__email', 'room__name')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display  = ('sender', 'room', 'text_preview', 'sent_at')
    search_fields = ('sender__email', 'text')

    @admin.display(description='Message')
    def text_preview(self, obj):
        return obj.text[:60] + '...' if len(obj.text) > 60 else obj.text
    
