# videos/admin.py
from django.contrib import admin
from .models import Video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display    = ('title', 'owner', 'status', 'file_size_mb', 'duration_min', 'uploaded_at')
    list_filter     = ('status', 'format')
    search_fields   = ('title', 'owner__email')
    readonly_fields = ('id', 'master_url', 'url_360p', 'url_720p', 'url_1080p', 'uploaded_at')
    actions         = ['mark_failed']

    @admin.display(description='Size (MB)')
    def file_size_mb(self, obj):
        if not obj.file_size:
            return '—'
        return f'{obj.file_size / (1024*1024):.1f} MB'

    @admin.display(description='Duration')
    def duration_min(self, obj):
        if not obj.duration:
            return '—'
        m = int(obj.duration // 60)
        s = int(obj.duration % 60)
        return f'{m}:{s:02d}'

    @admin.action(description='Mark selected as failed')
    def mark_failed(self, request, queryset):
        queryset.update(status='failed')
        
