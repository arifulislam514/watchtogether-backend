from django.shortcuts import render

# Create your views here.
# users/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from .models import User, FriendRequest
from .serializers import UserSerializer, FriendRequestSerializer


class UserProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/users/me/ — view and update own profile"""
    serializer_class   = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class FriendListView(generics.ListAPIView):
    """GET /api/friends/ — list all accepted friends"""
    serializer_class   = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Get IDs of all accepted friend connections
        sent     = FriendRequest.objects.filter(sender=user,    status='accepted').values_list('receiver_id', flat=True)
        received = FriendRequest.objects.filter(receiver=user,  status='accepted').values_list('sender_id',   flat=True)
        friend_ids = list(sent) + list(received)
        return User.objects.filter(id__in=friend_ids)


class FriendRequestListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/friend-requests/ — list pending received requests
    POST /api/friend-requests/ — send a friend request
    """
    serializer_class   = FriendRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only show requests received by current user
        return FriendRequest.objects.filter(
            receiver=self.request.user, status='pending'
        )

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)


class FriendRequestActionView(APIView):
    """PATCH /api/friend-requests/{id}/ — accept or decline"""
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        try:
            friend_request = FriendRequest.objects.get(
                id=pk, receiver=request.user, status='pending'
            )
        except FriendRequest.DoesNotExist:
            return Response(
                {'error': 'Request not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        action = request.data.get('action')  # 'accept' or 'decline'

        if action == 'accept':
            friend_request.status = 'accepted'
            friend_request.save()
            return Response({'status': 'Friend request accepted'})

        elif action == 'decline':
            friend_request.status = 'declined'
            friend_request.save()
            return Response({'status': 'Friend request declined'})

        return Response(
            {'error': 'Invalid action. Use accept or decline'},
            status=status.HTTP_400_BAD_REQUEST
        )


class UserSearchView(generics.ListAPIView):
    """GET /api/users/search/?q=name — search users by name or email"""
    serializer_class   = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        if not query:
            return User.objects.none()
        return User.objects.filter(
            Q(name__icontains=query) | Q(email__icontains=query)
        ).exclude(id=self.request.user.id)
        
