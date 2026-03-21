# videos/views.py
import os
import shutil
import threading
import logging
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.conf import settings
from .models import Video
from .serializers import VideoSerializer, VideoUploadSerializer, VideoUpdateSerializer
from .services import upload_to_r2

logger = logging.getLogger(__name__)


def delete_video_files(video):
    is_local = settings.R2_ENDPOINT_URL.startswith('https://your-account')
    if is_local:
        video_dir = os.path.join(settings.MEDIA_ROOT, 'videos', str(video.id))
        if os.path.exists(video_dir):
            shutil.rmtree(video_dir)
    else:
        from .services import get_r2_client
        client = get_r2_client()
        prefix = f"videos/{video.id}/"
        response = client.list_objects_v2(Bucket=settings.R2_BUCKET_NAME, Prefix=prefix)
        objects = response.get('Contents', [])
        if objects:
            client.delete_objects(
                Bucket=settings.R2_BUCKET_NAME,
                Delete={'Objects': [{'Key': o['Key']} for o in objects]}
            )

def run_transcode_in_thread(video_id):
    def _run():
        try:
            logger.info(f"[Thread] Starting transcode: {video_id}")
            from videos.tasks import transcode_video_sync  # ✅ use sync version
            transcode_video_sync(video_id)
            logger.info(f"[Thread] Transcode complete: {video_id}")
        except Exception as e:
            logger.error(f"[Thread] Transcode failed: {e}", exc_info=True)

    t = threading.Thread(target=_run, daemon=True)
    t.start()


class VideoListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def get(self, request):
        videos = Video.objects.filter(owner=request.user)
        return Response(VideoSerializer(videos, many=True, context={'request': request}).data)

    def post(self, request):
        serializer = VideoUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        file        = serializer.validated_data['file']
        title       = serializer.validated_data['title']
        description = serializer.validated_data.get('description', '')

        video = Video.objects.create(
            owner=request.user,
            title=title,
            description=description,
            file_size=file.size,
            format=file.name.split('.')[-1].lower(),
            status='uploading',
        )

        key          = f"videos/{video.id}/original.{video.format}"
        original_url = upload_to_r2(file, key)

        video.original_url = original_url
        video.status       = 'processing'
        video.progress     = 5
        video.stage        = 'Starting...'
        video.save()

        # ✅ Run in background thread — no Celery needed
        run_transcode_in_thread(str(video.id))

        return Response(
            VideoSerializer(video, context={'request': request}).data,
            status=status.HTTP_202_ACCEPTED
        )


class VideoDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, user):
        return get_object_or_404(Video, pk=pk, owner=user)

    def get(self, request, pk):
        video = self.get_object(pk, request.user)
        return Response(VideoSerializer(video, context={'request': request}).data)

    def patch(self, request, pk):
        video      = self.get_object(pk, request.user)
        serializer = VideoUpdateSerializer(video, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(VideoSerializer(video, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        video = self.get_object(pk, request.user)
        delete_video_files(video)
        video.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    