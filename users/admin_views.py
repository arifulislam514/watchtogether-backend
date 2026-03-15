# users/admin_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.db.models import Count
from users.models import User
from videos.models import Video
from rooms.models import Room
from users.serializers import UserSerializer
from videos.serializers import VideoSerializer
from rooms.serializers import RoomSerializer


class IsStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff


class AdminStatsView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        return Response({
            'total_users':  User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'banned_users': User.objects.filter(is_active=False).count(),
            'total_videos': Video.objects.count(),
            'ready_videos': Video.objects.filter(status='ready').count(),
            'total_rooms':  Room.objects.count(),
            'active_rooms': Room.objects.filter(is_active=True).count(),
        })


class AdminUserListView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        users = User.objects.all().order_by('-created_at')
        return Response(UserSerializer(users, many=True).data)


class AdminUserActionView(APIView):
    permission_classes = [IsStaff]

    def patch(self, request, user_id):
        """Ban or unban a user"""
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)

        if user.is_superuser:
            return Response({'error': 'Cannot modify superuser'}, status=400)

        action = request.data.get('action')
        if action == 'ban':
            user.is_active = False
            user.save()
            return Response({'message': f'{user.email} banned'})
        elif action == 'unban':
            user.is_active = True
            user.save()
            return Response({'message': f'{user.email} unbanned'})

        return Response({'error': 'Invalid action'}, status=400)


class AdminVideoListView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        videos = Video.objects.select_related('owner').order_by('-uploaded_at')
        return Response(VideoSerializer(videos, many=True).data)


class AdminVideoDeleteView(APIView):
    permission_classes = [IsStaff]

    def delete(self, request, video_id):
        import os, shutil
        from django.conf import settings
        try:
            video = Video.objects.get(id=video_id)
        except Video.DoesNotExist:
            return Response({'error': 'Video not found'}, status=404)

        # Delete files
        video_dir = os.path.join(settings.MEDIA_ROOT, 'videos', str(video.id))
        if os.path.exists(video_dir):
            shutil.rmtree(video_dir)

        video.delete()
        return Response(status=204)


class AdminRoomListView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        rooms = Room.objects.select_related('host').order_by('-created_at')
        return Response(RoomSerializer(rooms, many=True).data)


class AdminRoomActionView(APIView):
    permission_classes = [IsStaff]

    def patch(self, request, room_id):
        """Force close a room"""
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({'error': 'Room not found'}, status=404)

        room.is_active = False
        room.save()
        return Response({'message': f'Room "{room.name}" closed'})
    
