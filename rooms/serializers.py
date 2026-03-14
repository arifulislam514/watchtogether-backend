# rooms/serializers.py
from rest_framework import serializers
from django.contrib.auth.hashers import make_password, check_password
from .models import Room, RoomMember, Message
from videos.serializers import VideoSerializer


class RoomMemberSerializer(serializers.ModelSerializer):
    user_name   = serializers.CharField(source='user.name',   read_only=True)
    user_avatar = serializers.ImageField(source='user.avatar', read_only=True)

    class Meta:
        model  = RoomMember
        fields = ('id', 'user', 'user_name', 'user_avatar', 'is_ready', 'joined_at')
        read_only_fields = ('id', 'user', 'joined_at')


class RoomSerializer(serializers.ModelSerializer):
    members      = RoomMemberSerializer(many=True, read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    host_name    = serializers.CharField(source='host.name', read_only=True)
    video_detail = VideoSerializer(source='video', read_only=True)

    class Meta:
        model  = Room
        fields = (
            'id', 'name', 'host', 'host_name',
            'video', 'video_detail',
            'invite_token', 'max_members',
            'member_count', 'members',
            'is_active', 'created_at',
        )
        read_only_fields = ('id', 'host', 'invite_token', 'created_at')


class RoomCreateSerializer(serializers.ModelSerializer):
    """Used for POST — creating a room"""
    password = serializers.CharField(write_only=True, min_length=4)

    class Meta:
        model  = Room
        fields = ('id', 'name', 'password', 'max_members')

    def validate_max_members(self, value):
        if value < 2 or value > 15:
            raise serializers.ValidationError('Max members must be between 2 and 15.')
        return value

    def create(self, validated_data):
        # Hash the password before saving
        validated_data['password'] = make_password(validated_data['password'])
        validated_data['host'] = self.context['request'].user
        return super().create(validated_data)


class JoinRoomSerializer(serializers.Serializer):
    """Used for POST /rooms/{id}/join/"""
    password     = serializers.CharField(required=False, allow_blank=True)
    invite_token = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        if not data.get('password') and not data.get('invite_token'):
            raise serializers.ValidationError(
                'Provide either a password or an invite token.'
            )
        return data


class MessageSerializer(serializers.ModelSerializer):
    sender_name   = serializers.CharField(source='sender.name',   read_only=True)
    sender_avatar = serializers.ImageField(source='sender.avatar', read_only=True)

    class Meta:
        model  = Message
        fields = ('id', 'sender', 'sender_name', 'sender_avatar', 'text', 'sent_at')
        read_only_fields = ('id', 'sender', 'sent_at')
        
