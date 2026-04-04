# videos/apps.py
from django.apps import AppConfig


class VideosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'videos'

    def ready(self):
        import os
        # ✅ Only retry stuck videos on the web server (Render)
        # Railway runs Celery worker — it should NOT retry stuck videos
        # Detect by checking if this is a web process (has PORT env var)
        if not os.environ.get('PORT'):
            return

        import threading
        import logging
        logger = logging.getLogger(__name__)

        def retry_stuck_videos():
            import time
            time.sleep(15)
            try:
                from videos.models import Video
                # ✅ Only retry videos stuck in 'processing' for more than 10 minutes
                from django.utils import timezone
                from datetime import timedelta
                cutoff = timezone.now() - timedelta(minutes=10)
                stuck = Video.objects.filter(
                    status='processing',
                    updated_at__lt=cutoff  # stuck for more than 10 min
                )
                if stuck.exists():
                    logger.info(f"[Startup] Found {stuck.count()} stuck video(s) — retrying...")
                    for video in stuck:
                        logger.info(f"[Startup] Retrying: {video.title}")
                        try:
                            from videos.tasks import transcode_video
                            transcode_video.delay(str(video.id))
                        except Exception as e:
                            logger.error(f"[Startup] Retry failed for {video.id}: {e}")
            except Exception as e:
                logger.error(f"[Startup] Stuck video check failed: {e}")

        t = threading.Thread(target=retry_stuck_videos, daemon=True)
        t.start()
        
