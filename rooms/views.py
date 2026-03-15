# rooms/views.py
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth.hashers import check_password
from .models import Room, RoomMember, Message
from .serializers import (
    RoomSerializer, RoomCreateSerializer, JoinRoomSerializer
)


class RoomListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        hosted = Room.objects.filter(host=request.user, is_active=True)
        joined = Room.objects.filter(members__user=request.user, is_active=True)
        rooms  = (hosted | joined).distinct()
        return Response(RoomSerializer(rooms, many=True).data)

    def post(self, request):
        serializer = RoomCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        room = serializer.save()
        RoomMember.objects.create(room=room, user=request.user)
        return Response(RoomSerializer(room).data, status=status.HTTP_201_CREATED)


class RoomDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(Room, pk=pk, is_active=True)

    def get(self, request, pk):
        return Response(RoomSerializer(self.get_object(pk)).data)

    def patch(self, request, pk):
        room = self.get_object(pk)
        if room.host != request.user:
            return Response({'error': 'Only host can update.'}, status=status.HTTP_403_FORBIDDEN)
        video_id = request.data.get('video')
        if video_id:
            from videos.models import Video
            video = get_object_or_404(Video, id=video_id, owner=request.user, status='ready')
            room.video = video
            room.save()
        return Response(RoomSerializer(room).data)

    def delete(self, request, pk):
        """Host closes the room permanently — shown as 'Close Room' in UI"""
        room = self.get_object(pk)
        if room.host != request.user:
            return Response({'error': 'Only host can close the room.'}, status=status.HTTP_403_FORBIDDEN)
        room.is_active = False
        room.save()
        RoomMember.objects.filter(room=room).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class JoinRoomView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        room = get_object_or_404(Room, pk=pk, is_active=True)

        if RoomMember.objects.filter(room=room, user=request.user).exists():
            return Response({'error': 'Already in this room.'}, status=status.HTTP_400_BAD_REQUEST)

        if room.is_full:
            return Response({'error': 'Room is full.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = JoinRoomSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        password     = serializer.validated_data.get('password', '')
        invite_token = serializer.validated_data.get('invite_token', '')

        password_valid     = password     and check_password(password, room.password)
        invite_token_valid = invite_token and invite_token == room.invite_token

        if not password_valid and not invite_token_valid:
            return Response({'error': 'Invalid password or invite token.'}, status=status.HTTP_403_FORBIDDEN)

        RoomMember.objects.create(room=room, user=request.user)
        return Response(RoomSerializer(room).data, status=status.HTTP_201_CREATED)


class LeaveRoomView(APIView):
    """Any member leaves — just removes them. Room stays active."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        room   = get_object_or_404(Room, pk=pk)
        member = RoomMember.objects.filter(room=room, user=request.user).first()
        if member:
            member.delete()
        return Response({'message': 'Left room.'}, status=status.HTTP_200_OK)


class RemoveMemberView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk, user_id):
        room = get_object_or_404(Room, pk=pk, is_active=True)
        if room.host != request.user:
            return Response({'error': 'Only host can remove members.'}, status=status.HTTP_403_FORBIDDEN)
        if str(user_id) == str(request.user.id):
            return Response({'error': 'Cannot remove yourself.'}, status=status.HTTP_400_BAD_REQUEST)
        member = get_object_or_404(RoomMember, room=room, user_id=user_id)
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReadyToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        room   = get_object_or_404(Room, pk=pk, is_active=True)
        member = get_object_or_404(RoomMember, room=room, user=request.user)
        member.is_ready = not member.is_ready
        member.save()
        all_ready = not room.members.filter(is_ready=False).exists()
        return Response({'is_ready': member.is_ready, 'all_ready': all_ready})
    
