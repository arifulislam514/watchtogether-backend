# videos/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from .models import Video
from .serializers import VideoSerializer, VideoUploadSerializer, VideoUpdateSerializer
from .services import upload_to_r2
from .tasks import transcode_video


class VideoListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]  # needed for file uploads

    def get(self, request):
        """GET /api/videos/ — list current user's videos"""
        videos = Video.objects.filter(owner=request.user)
        serializer = VideoSerializer(videos, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        """POST /api/videos/ — upload a new video"""
        serializer = VideoUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        file  = serializer.validated_data['file']
        title = serializer.validated_data['title']
        description = serializer.validated_data.get('description', '')

        # Create video record immediately with status=uploading
        video = Video.objects.create(
            owner=request.user,
            title=title,
            description=description,
            file_size=file.size,
            format=file.name.split('.')[-1].lower(),
            status='uploading',
        )

        # Upload original to R2
        key = f"videos/{video.id}/original.{video.format}"
        original_url = upload_to_r2(file, key)

        # Update video with URL and trigger background transcoding
        video.original_url = original_url
        video.status = 'processing'
        video.save()

        # Fire Celery task — non-blocking
        transcode_video.delay(str(video.id))

        return Response(
            VideoSerializer(video, context={'request': request}).data,
            status=status.HTTP_202_ACCEPTED
        )


class VideoDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, user):
        return get_object_or_404(Video, pk=pk, owner=user)

    def get(self, request, pk):
        """GET /api/videos/{id}/ — get video detail + status polling"""
        video = self.get_object(pk, request.user)
        return Response(VideoSerializer(video, context={'request': request}).data)

    def patch(self, request, pk):
        """PATCH /api/videos/{id}/ — update title or description"""
        video = self.get_object(pk, request.user)
        serializer = VideoUpdateSerializer(video, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(VideoSerializer(video, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """DELETE /api/videos/{id}/ — delete video"""
        video = self.get_object(pk, request.user)
        video.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
