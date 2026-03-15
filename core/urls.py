# core/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from users.admin_views import (
    AdminStatsView, AdminUserListView, AdminUserActionView,
    AdminVideoListView, AdminVideoDeleteView,
    AdminRoomListView, AdminRoomActionView,
)

urlpatterns = [
    path('admin/',    admin.site.urls),
    path('api/auth/', include('djoser.urls')),
    path('api/auth/', include('djoser.urls.jwt')),
    path('api/',      include('users.urls')),
    path('api/',      include('videos.urls')),
    path('api/',      include('rooms.urls')),

    # Admin API
    path('api/admin/stats/',                    AdminStatsView.as_view()),
    path('api/admin/users/',                    AdminUserListView.as_view()),
    path('api/admin/users/<uuid:user_id>/',     AdminUserActionView.as_view()),
    path('api/admin/videos/',                   AdminVideoListView.as_view()),
    path('api/admin/videos/<uuid:video_id>/',   AdminVideoDeleteView.as_view()),
    path('api/admin/rooms/',                    AdminRoomListView.as_view()),
    path('api/admin/rooms/<uuid:room_id>/',     AdminRoomActionView.as_view()),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

