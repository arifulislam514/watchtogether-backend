# rooms/urls.py
from django.urls import path
from .views import (
    RoomListCreateView,
    RoomDetailView,
    JoinRoomView,
    RemoveMemberView,
    ReadyToggleView,
)

urlpatterns = [
    path('rooms/',                              RoomListCreateView.as_view(), name='room-list-create'),
    path('rooms/<uuid:pk>/',                    RoomDetailView.as_view(),     name='room-detail'),
    path('rooms/<uuid:pk>/join/',               JoinRoomView.as_view(),       name='room-join'),
    path('rooms/<uuid:pk>/ready/',              ReadyToggleView.as_view(),    name='room-ready'),
    path('rooms/<uuid:pk>/members/<uuid:user_id>/', RemoveMemberView.as_view(), name='room-remove-member'),
]
