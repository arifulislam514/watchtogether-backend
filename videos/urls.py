# videos/urls.py
from django.urls import path
from .views import VideoListCreateView, VideoDetailView, VideoPresignedUploadView, VideoConfirmUploadView

urlpatterns = [
    path('videos/',                              VideoListCreateView.as_view()),
    path('videos/<uuid:pk>/',                    VideoDetailView.as_view()),
    path('videos/presigned-upload/',             VideoPresignedUploadView.as_view()),
    path('videos/<uuid:video_id>/confirm-upload/', VideoConfirmUploadView.as_view()),
]