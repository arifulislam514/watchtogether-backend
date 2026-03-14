# videos/serializers.py
from rest_framework import serializers
from .models import Video


class VideoUploadSerializer(serializers.ModelSerializer):
    """Used for POST — uploading a new video"""
    file = serializers.FileField(write_only=True)

    class Meta:
        model  = Video
        fields = ('id', 'title', 'description', 'file')

    def validate_file(self, value):
        # Check format
        allowed_formats = ['video/mp4', 'video/x-matroska']
        if value.content_type not in allowed_formats:
            raise serializers.ValidationError('Only mp4 and mkv files are allowed.')

        # Check size — 4GB max
        max_size = 4 * 1024 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError('File size must be under 4GB.')

        return value


class VideoSerializer(serializers.ModelSerializer):
    """Used for GET — reading video data"""
    owner_name = serializers.CharField(source='owner.name', read_only=True)

    class Meta:
        model  = Video
        fields = (
            'id', 'title', 'description',
            'owner', 'owner_name',
            'master_url', 'url_360p', 'url_720p', 'url_1080p',
            'file_size', 'duration', 'format',
            'status', 'is_ready',
            'uploaded_at',
        )
        read_only_fields = (
            'id', 'owner', 'master_url', 'url_360p',
            'url_720p', 'url_1080p', 'status', 'uploaded_at'
        )


class VideoUpdateSerializer(serializers.ModelSerializer):
    """Used for PATCH — only allow title and description updates"""
    class Meta:
        model  = Video
        fields = ('title', 'description')
        
