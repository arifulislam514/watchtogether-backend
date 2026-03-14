# rooms/models.py
import uuid
import secrets
from django.db import models
from django.conf import settings


class Room(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hosted_rooms')
    video        = models.ForeignKey('videos.Video', on_delete=models.SET_NULL, null=True, blank=True, related_name='rooms')
    name         = models.CharField(max_length=100)

    # Room access
    password     = models.CharField(max_length=128)         # stored as plain for simplicity, hashed below
    invite_token = models.CharField(max_length=64, unique=True, blank=True)

    # Settings
    max_members  = models.PositiveIntegerField(default=10)
    is_active    = models.BooleanField(default=True)

    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} (host: {self.host.email})"

    def save(self, *args, **kwargs):
        # Auto-generate invite token on creation
        if not self.invite_token:
            self.invite_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def member_count(self):
        return self.members.count()

    @property
    def is_full(self):
        return self.member_count >= self.max_members


class RoomMember(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room      = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='members')
    user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='room_memberships')
    is_ready  = models.BooleanField(default=False)  # for the ready-gate feature
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # A user can only be in a room once
        unique_together = ('room', 'user')

    def __str__(self):
        return f"{self.user.email} in {self.room.name}"


class Message(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room      = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='messages')
    sender    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='messages')
    text      = models.TextField()
    sent_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sent_at']

    def __str__(self):
        return f"{self.sender.email}: {self.text[:50]}"
    