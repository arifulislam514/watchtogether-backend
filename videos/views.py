# videos/views.py
import os
import shutil
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
from django.db import transaction
from .tasks import transcode_video

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

        # Trigger Celery task after DB commit
        transaction.on_commit(lambda: transcode_video.delay(str(video.id)))

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
    

class VideoPresignedUploadView(APIView):
    """
    Step 1: Frontend requests a presigned URL
    Step 2: Frontend uploads directly to R2
    Step 3: Frontend calls VideoConfirmUploadView to trigger transcoding
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        filename    = request.data.get('filename', '')
        file_size   = int(request.data.get('file_size', 0))
        title       = request.data.get('title', filename.rsplit('.', 1)[0])
        description = request.data.get('description', '')

        if not filename:
            return Response({'error': 'filename required'}, status=400)

        ext = filename.split('.')[-1].lower()
        if ext not in ['mp4', 'mkv']:
            return Response({'error': 'Only mp4 and mkv allowed'}, status=400)

        if file_size > 4 * 1024 * 1024 * 1024:
            return Response({'error': 'File must be under 4GB'}, status=400)

        # Create video record immediately
        video = Video.objects.create(
            owner=request.user,
            title=title,
            description=description,
            file_size=file_size,
            format=ext,
            status='uploading',
            progress=0,
            stage='Waiting for upload...',
        )

        key = f"videos/{video.id}/original.{ext}"

        # Generate presigned URL — valid for 2 hours (large files need time)
        from .services import get_r2_client
        client = get_r2_client()
        presigned_url = client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket':      settings.R2_BUCKET_NAME,
                'Key':         key,
                'ContentType': 'video/mp4' if ext == 'mp4' else 'video/x-matroska',
            },
            ExpiresIn=7200,
        )

        return Response({
            'video_id':     str(video.id),
            'upload_url':   presigned_url,
            'key':          key,
        }, status=201)


class VideoConfirmUploadView(APIView):
    """
    Called after frontend finishes uploading directly to R2.
    Sets original_url and kicks off transcoding.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, video_id):
        video = get_object_or_404(Video, id=video_id, owner=request.user)

        if video.status != 'uploading':
            return Response({'error': 'Video not in uploading state'}, status=400)

        key = f"videos/{video.id}/original.{video.format}"
        video.original_url = f"{settings.R2_PUBLIC_URL}/{key}"
        video.status       = 'processing'
        video.progress     = 5
        video.stage        = 'Starting...'
        video.save()

        transaction.on_commit(lambda: transcode_video.delay(str(video.id)))

        return Response(VideoSerializer(video).data)
    
