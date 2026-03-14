# rooms/views.py
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth.hashers import check_password
from .models import Room, RoomMember, Message
from .serializers import (
    RoomSerializer, RoomCreateSerializer,
    JoinRoomSerializer, RoomMemberSerializer
)


class RoomListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """GET /api/rooms/ — list rooms where user is host or member"""
        hosted   = Room.objects.filter(host=request.user, is_active=True)
        joined   = Room.objects.filter(members__user=request.user, is_active=True)
        rooms    = (hosted | joined).distinct()
        return Response(RoomSerializer(rooms, many=True).data)

    def post(self, request):
        """POST /api/rooms/ — create a new room"""
        serializer = RoomCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        room = serializer.save()

        # Host automatically joins as first member
        RoomMember.objects.create(room=room, user=request.user)

        return Response(RoomSerializer(room).data, status=status.HTTP_201_CREATED)


class RoomDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(Room, pk=pk, is_active=True)

    def get(self, request, pk):
        """GET /api/rooms/{id}/ — get room details"""
        room = self.get_object(pk)
        return Response(RoomSerializer(room).data)

    def patch(self, request, pk):
        """PATCH /api/rooms/{id}/ — host updates video selection"""
        room = self.get_object(pk)

        # Only host can update the room
        if room.host != request.user:
            return Response(
                {'error': 'Only the host can update the room.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Only allow video field to be updated here
        video_id = request.data.get('video')
        if video_id:
            from videos.models import Video
            video = get_object_or_404(Video, id=video_id, owner=request.user, status='ready')
            room.video = video
            room.save()

        return Response(RoomSerializer(room).data)

    def delete(self, request, pk):
        """DELETE /api/rooms/{id}/ — host closes the room"""
        room = self.get_object(pk)

        if room.host != request.user:
            return Response(
                {'error': 'Only the host can close the room.'},
                status=status.HTTP_403_FORBIDDEN
            )

        room.is_active = False
        room.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class JoinRoomView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        """POST /api/rooms/{id}/join/ — join via password or invite token"""
        room = get_object_or_404(Room, pk=pk, is_active=True)

        # Already a member?
        if RoomMember.objects.filter(room=room, user=request.user).exists():
            return Response(
                {'error': 'You are already in this room.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Room full?
        if room.is_full:
            return Response(
                {'error': 'Room is full.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = JoinRoomSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        password     = serializer.validated_data.get('password', '')
        invite_token = serializer.validated_data.get('invite_token', '')

        # Validate access — password OR invite token
        password_valid     = password     and check_password(password, room.password)
        invite_token_valid = invite_token and invite_token == room.invite_token

        if not password_valid and not invite_token_valid:
            return Response(
                {'error': 'Invalid password or invite token.'},
                status=status.HTTP_403_FORBIDDEN
            )

        RoomMember.objects.create(room=room, user=request.user)
        return Response(RoomSerializer(room).data, status=status.HTTP_201_CREATED)


class RemoveMemberView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk, user_id):
        """DELETE /api/rooms/{id}/members/{user_id}/ — host removes a member"""
        room = get_object_or_404(Room, pk=pk, is_active=True)

        if room.host != request.user:
            return Response(
                {'error': 'Only the host can remove members.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Host can't remove themselves
        if str(user_id) == str(request.user.id):
            return Response(
                {'error': 'Host cannot remove themselves.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        member = get_object_or_404(RoomMember, room=room, user_id=user_id)
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReadyToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        """POST /api/rooms/{id}/ready/ — toggle ready state"""
        room   = get_object_or_404(Room, pk=pk, is_active=True)
        member = get_object_or_404(RoomMember, room=room, user=request.user)

        member.is_ready = not member.is_ready
        member.save()

        # Check if ALL members are ready
        all_ready = not room.members.filter(is_ready=False).exists()

        return Response({
            'is_ready':  member.is_ready,
            'all_ready': all_ready,
        })
        
