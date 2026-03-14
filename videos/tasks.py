# videos/tasks.py
from celery import shared_task
from .models import Video


@shared_task
def transcode_video(video_id):
    """
    Background task to transcode video into HLS format.
    Full implementation in Step 7 (Celery + FFmpeg).
    """
    try:
        video = Video.objects.get(id=video_id)
        # TODO: FFmpeg transcoding in Step 7
        # For now, mark as ready so we can test the upload flow
        video.status = 'ready'
        video.master_url = video.original_url  # temporary
        video.save()
    except Video.DoesNotExist:
        pass
    
