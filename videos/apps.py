# videos/apps.py
from django.apps import AppConfig


class VideosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'videos'

    def ready(self):
        """On startup, retry any videos stuck in 'processing' state."""
        import threading
        import logging
        logger = logging.getLogger(__name__)

        def retry_stuck_videos():
            import time
            time.sleep(10)  # wait for Django to fully start
            try:
                from videos.models import Video
                from videos.tasks import transcode_video_sync
                stuck = Video.objects.filter(status='processing')
                if stuck.exists():
                    logger.info(f"[Startup] Found {stuck.count()} stuck video(s) — retrying...")
                    for video in stuck:
                        logger.info(f"[Startup] Retrying: {video.title}")
                        try:
                            transcode_video_sync(str(video.id))
                        except Exception as e:
                            logger.error(f"[Startup] Retry failed for {video.id}: {e}")
            except Exception as e:
                logger.error(f"[Startup] Stuck video check failed: {e}")

        t = threading.Thread(target=retry_stuck_videos, daemon=False)
        t.start()
        
