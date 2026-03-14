# videos/tasks.py
import os
import subprocess
import tempfile
import shutil
import logging
import boto3
from celery import shared_task
from django.conf import settings
from botocore.config import Config
from .models import Video

logger = logging.getLogger(__name__)


def get_r2_client():
    return boto3.client(
        's3',
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='auto',
    )


def download_file(url, destination):
    """
    Downloads a file from a URL or copies from local media folder.
    Handles both local (development) and R2 (production) URLs.
    """
    if url.startswith('/media/'):
        local_path = os.path.join(
            settings.MEDIA_ROOT,
            url.replace('/media/', '', 1)
        )
        shutil.copy2(local_path, destination)
    else:
        import requests
        response = requests.get(url, stream=True)
        with open(destination, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)


def upload_hls_files(video_id, temp_dir):
    """
    Uploads all HLS files (.m3u8 and .ts) to storage.
    Returns master_url and dict of resolution URLs.
    """
    is_local = settings.R2_ENDPOINT_URL.startswith('https://your-account')

    for root, dirs, files in os.walk(temp_dir):
        for filename in files:
            file_path = os.path.join(root, filename)
            relative  = os.path.relpath(file_path, temp_dir)
            key       = f"videos/{video_id}/hls/{relative}".replace('\\', '/')

            if is_local:
                dest = os.path.join(settings.MEDIA_ROOT, key)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(file_path, dest)
            else:
                client = get_r2_client()
                content_type = (
                    'application/vnd.apple.mpegurl'
                    if filename.endswith('.m3u8') else 'video/mp2t'
                )
                client.upload_file(
                    file_path,
                    settings.R2_BUCKET_NAME,
                    key,
                    ExtraArgs={'ContentType': content_type}
                )

    if is_local:
        master_url = f"/media/videos/{video_id}/hls/master.m3u8"
        urls = {
            '360p':  f"/media/videos/{video_id}/hls/360p/playlist.m3u8",
            '720p':  f"/media/videos/{video_id}/hls/720p/playlist.m3u8",
            '1080p': f"/media/videos/{video_id}/hls/1080p/playlist.m3u8",
        }
    else:
        base = f"{settings.R2_ENDPOINT_URL}/{settings.R2_BUCKET_NAME}"
        master_url = f"{base}/videos/{video_id}/hls/master.m3u8"
        urls = {
            '360p':  f"{base}/videos/{video_id}/hls/360p/playlist.m3u8",
            '720p':  f"{base}/videos/{video_id}/hls/720p/playlist.m3u8",
            '1080p': f"{base}/videos/{video_id}/hls/1080p/playlist.m3u8",
        }

    return master_url, urls


def get_video_duration(input_path):
    """Uses ffprobe to get video duration in seconds."""
    result = subprocess.run([
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        input_path
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0


@shared_task(bind=True, max_retries=3)
def transcode_video(self, video_id):
    """
    Main Celery task:
    1. Download original video
    2. Transcode to HLS at 360p, 720p, 1080p using FFmpeg
    3. Upload all segments to storage
    4. Update Video model with URLs and status=ready
    """
    logger.info(f"Starting transcoding for video: {video_id}")

    try:
        video = Video.objects.get(id=video_id)
        logger.info(f"Video found: {video.title}")

        video.status = 'processing'
        video.save()

        # Create temp working directory
        temp_dir   = tempfile.mkdtemp(prefix=f'transcode_{video_id}_')
        input_path = os.path.join(temp_dir, f'original.{video.format}')
        output_dir = os.path.join(temp_dir, 'hls')
        os.makedirs(output_dir, exist_ok=True)

        try:
            # ── Step 1: Download original ──────────────────────
            logger.info("Downloading original video...")
            download_file(video.original_url, input_path)

            # ── Step 2: Get duration ───────────────────────────
            duration = get_video_duration(input_path)
            video.duration = duration
            video.save()
            logger.info(f"Video duration: {duration}s")

            # ── Step 3: FFmpeg — 3 separate commands ───────────
            resolutions = [
                ('360p',  '640x360',   '800k',  '128k'),
                ('720p',  '1280x720',  '2500k', '128k'),
                ('1080p', '1920x1080', '5000k', '128k'),
            ]

            for label, size, vbitrate, abitrate in resolutions:
                res_dir = os.path.join(output_dir, label)
                os.makedirs(res_dir, exist_ok=True)

                cmd = [
                    'ffmpeg', '-i', input_path,
                    '-vf', f'scale={size}',
                    '-c:v', 'libx264',
                    '-b:v', vbitrate,
                    '-c:a', 'aac',
                    '-b:a', abitrate,
                    '-f', 'hls',
                    '-hls_time', '6',
                    '-hls_playlist_type', 'vod',
                    '-hls_segment_filename', os.path.join(res_dir, 'segment%03d.ts'),
                    os.path.join(res_dir, 'playlist.m3u8'),
                    '-y'
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode != 0:
                    raise Exception(f'FFmpeg failed for {label}: {result.stderr[-500:]}')

                logger.info(f"Transcoded {label} successfully")

            # ── Step 4: Create master.m3u8 manually ───────────
            master_content = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360
360p/playlist.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720
720p/playlist.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080
1080p/playlist.m3u8
"""
            master_path = os.path.join(output_dir, 'master.m3u8')
            with open(master_path, 'w') as f:
                f.write(master_content.strip())

            logger.info("Master playlist created")

            # ── Step 5: Upload all HLS files to storage ────────
            logger.info("Uploading HLS files to storage...")
            master_url, resolution_urls = upload_hls_files(video_id, output_dir)

            # ── Step 6: Update Video model ─────────────────────
            video.master_url = master_url
            video.url_360p   = resolution_urls['360p']
            video.url_720p   = resolution_urls['720p']
            video.url_1080p  = resolution_urls['1080p']
            video.status     = 'ready'
            video.save()

            logger.info(f"Transcoding complete for video: {video_id}")

        finally:
            # Always clean up temp files regardless of success or failure
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info("Temp files cleaned up")

    except Video.DoesNotExist:
        logger.error(f"Video not found in DB: {video_id}")

    except Exception as exc:
        logger.error(f"Transcoding failed: {exc}")
        try:
            video = Video.objects.get(id=video_id)
            video.status = 'failed'
            video.save()
        except Video.DoesNotExist:
            pass
        raise self.retry(exc=exc, countdown=60)
    
