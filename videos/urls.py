# videos/urls.py
from django.urls import path
from .views import VideoListCreateView, VideoDetailView

urlpatterns = [
    path('videos/',          VideoListCreateView.as_view(), name='video-list-create'),
    path('videos/<uuid:pk>/',VideoDetailView.as_view(),     name='video-detail'),
]
