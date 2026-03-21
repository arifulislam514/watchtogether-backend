# videos/models.py
import uuid
from django.db import models
from django.conf import settings


class Video(models.Model):
    STATUS_CHOICES = [
        ('uploading',  'Uploading'),
        ('processing', 'Processing'),
        ('ready',      'Ready'),
        ('failed',     'Failed'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='videos')
    title        = models.CharField(max_length=255)
    description  = models.TextField(blank=True)

    # Original uploaded file stored on Cloudflare R2
    original_url = models.URLField(blank=True)

    # HLS transcoded versions — filled after Celery task completes
    master_url   = models.URLField(blank=True)  # master.m3u8 — this is what the player loads
    url_360p     = models.URLField(blank=True)
    url_720p     = models.URLField(blank=True)
    url_1080p    = models.URLField(blank=True)

    # Metadata
    file_size    = models.BigIntegerField(default=0)  # bytes
    duration     = models.FloatField(default=0)       # seconds
    format       = models.CharField(max_length=10, blank=True)  # mp4, mkv

    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploading')
    progress     = models.IntegerField(default=0)   # 0-100 percent
    stage        = models.CharField(max_length=50, blank=True)  # current processing stage
    uploaded_at  = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.title} ({self.owner.email})"

    @property
    def is_ready(self):
        return self.status == 'ready'
