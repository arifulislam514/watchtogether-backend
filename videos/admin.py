# videos/admin.py
from django.contrib import admin
from .models import Video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display  = ('title', 'owner', 'status', 'file_size', 'uploaded_at')
    list_filter   = ('status', 'format')
    search_fields = ('title', 'owner__email')
    readonly_fields = ('id', 'master_url', 'url_360p', 'url_720p', 'url_1080p', 'uploaded_at')

