# users/urls.py
from django.urls import path
from .views import (
    UserProfileView,
    FriendListView,
    FriendRequestListCreateView,
    FriendRequestActionView,
    UserSearchView,
)

urlpatterns = [
    path('users/me/',                UserProfileView.as_view(),            name='user-profile'),
    path('users/search/',            UserSearchView.as_view(),             name='user-search'),
    path('friends/',                 FriendListView.as_view(),             name='friend-list'),
    path('friend-requests/',         FriendRequestListCreateView.as_view(),name='friend-requests'),
    path('friend-requests/<uuid:pk>/',FriendRequestActionView.as_view(),  name='friend-request-action'),
]