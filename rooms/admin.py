# rooms/admin.py
from django.contrib import admin
from .models import Room, RoomMember, Message


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display  = ('name', 'host', 'member_count', 'is_active', 'created_at')
    list_filter   = ('is_active',)
    search_fields = ('name', 'host__email')
    readonly_fields = ('id', 'invite_token', 'created_at')


@admin.register(RoomMember)
class RoomMemberAdmin(admin.ModelAdmin):
    list_display  = ('user', 'room', 'is_ready', 'joined_at')
    list_filter   = ('is_ready',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display  = ('sender', 'room', 'text', 'sent_at')
    search_fields = ('sender__email', 'text')
    
