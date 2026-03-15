# videos/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Video
from .tasks import transcode_video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display  = ('title', 'owner', 'status_badge', 'duration_display', 'file_size_display', 'uploaded_at')
    list_filter   = ('status', 'format')
    search_fields = ('title', 'owner__email', 'description')
    ordering      = ('-uploaded_at',)
    readonly_fields = (
        'id', 'uploaded_at', 'updated_at',
        'master_url', 'url_360p', 'url_720p', 'url_1080p',
        'duration', 'file_size',
    )

    fieldsets = (
        ('Info',        {'fields': ('id', 'owner', 'title', 'description')}),
        ('Source',      {'fields': ('original_url', 'format', 'file_size')}),
        ('HLS URLs',    {'fields': ('master_url', 'url_360p', 'url_720p', 'url_1080p')}),
        ('Metadata',    {'fields': ('duration', 'status')}),
        ('Timestamps',  {'fields': ('uploaded_at', 'updated_at')}),
    )

    actions = ['retranscode_videos', 'mark_failed']

    def status_badge(self, obj):
        colours = {
            'uploading':  ('#6366f1', 'Uploading'),
            'processing': ('#f59e0b', 'Processing'),
            'ready':      ('#10b981', 'Ready'),
            'failed':     ('#ef4444', 'Failed'),
        }
        colour, label = colours.get(obj.status, ('#6b7280', obj.status))
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;">{}</span>',
            colour, label
        )
    status_badge.short_description = 'Status'

    def duration_display(self, obj):
        if not obj.duration:
            return '—'
        m, s = divmod(int(obj.duration), 60)
        return f'{m}m {s}s'
    duration_display.short_description = 'Duration'

    def file_size_display(self, obj):
        if not obj.file_size:
            return '—'
        mb = obj.file_size / (1024 * 1024)
        return f'{mb:.1f} MB'
    file_size_display.short_description = 'Size'

    @admin.action(description='Re-transcode selected videos')
    def retranscode_videos(self, request, queryset):
        count = 0
        for video in queryset:
            transcode_video.delay(str(video.id))
            count += 1
        self.message_user(request, f'Queued {count} video(s) for re-transcoding.')

    @admin.action(description='Mark selected videos as failed')
    def mark_failed(self, request, queryset):
        updated = queryset.update(status='failed')
        self.message_user(request, f'{updated} video(s) marked as failed.')
