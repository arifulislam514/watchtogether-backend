# users/serializers.py
from rest_framework import serializers
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from .models import User, FriendRequest


class UserCreateSerializer(BaseUserCreateSerializer):
    """Used by Djoser for registration — POST /api/auth/users/"""

    class Meta(BaseUserCreateSerializer.Meta):
        model  = User
        fields = ('id', 'email', 'name', 'password')


class UserSerializer(serializers.ModelSerializer):
    """Used for profile — GET /api/auth/users/me/"""
    friends_count = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ('id', 'email', 'name', 'avatar', 'friends_count', 'created_at')
        read_only_fields = ('id', 'email', 'created_at')

    def get_friends_count(self, obj):
        return FriendRequest.objects.filter(
            sender=obj, status='accepted'
        ).count() + FriendRequest.objects.filter(
            receiver=obj, status='accepted'
        ).count()


class FriendRequestSerializer(serializers.ModelSerializer):
    sender_name   = serializers.CharField(source='sender.name',   read_only=True)
    receiver_name = serializers.CharField(source='receiver.name', read_only=True)
    sender_avatar = serializers.ImageField(source='sender.avatar', read_only=True)

    class Meta:
        model  = FriendRequest
        fields = (
            'id', 'sender', 'sender_name', 'sender_avatar',
            'receiver', 'receiver_name', 'status', 'created_at'
        )
        read_only_fields = ('id', 'sender', 'status', 'created_at')