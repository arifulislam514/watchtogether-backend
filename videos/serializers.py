# videos/serializers.py
from rest_framework import serializers
from .models import Video


class VideoUploadSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)

    class Meta:
        model  = Video
        fields = ('id', 'title', 'description', 'file')

    def validate_file(self, value):
        # ✅ Check by extension as well — browsers send inconsistent
        # content types for MKV (video/x-matroska, video/mkv,
        # application/octet-stream, or even video/webm on some browsers)
        name = value.name.lower()
        allowed_extensions = ('.mp4', '.mkv')
        allowed_mimetypes  = (
            'video/mp4',
            'video/x-matroska',  # standard MKV
            'video/mkv',         # non-standard but common
            'video/webm',        # some browsers report MKV as webm
            'application/octet-stream',  # generic binary (check ext instead)
        )

        ext_ok  = name.endswith(allowed_extensions)
        mime_ok = value.content_type in allowed_mimetypes

        if not ext_ok and not mime_ok:
            raise serializers.ValidationError(
                'Only mp4 and mkv files are allowed.'
            )

        if not ext_ok:
            raise serializers.ValidationError(
                'Only .mp4 and .mkv file extensions are allowed.'
            )

        # Check size — 4GB max
        if value.size > 4 * 1024 * 1024 * 1024:
            raise serializers.ValidationError('File size must be under 4GB.')

        return value


class VideoSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.name', read_only=True)

    class Meta:
        model  = Video
        fields = (
            'id', 'title', 'description',
            'owner', 'owner_name',
            'master_url', 'url_360p', 'url_480p', 'url_720p', 'url_1080p',
            'qualities',
            'file_size', 'duration', 'format',
            'status', 'is_ready',
            'progress', 'stage',
            'uploaded_at',
        )
        read_only_fields = (
            'id', 'owner', 'master_url', 'url_360p', 'url_480p',
            'url_720p', 'url_1080p', 'status', 'uploaded_at'
        )


class VideoUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Video
        fields = ('title', 'description')
