# videos/tasks.py
import os
import json
import subprocess
import tempfile
import shutil
import logging
import boto3
from celery import shared_task
from django.conf import settings
from botocore.config import Config
from .models import Video
import os as _os

import shutil as _shutil
_BIN_FFMPEG  = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'bin', 'ffmpeg')
_BIN_FFPROBE = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'bin', 'ffprobe')
FFMPEG  = _BIN_FFMPEG  if _os.path.isfile(_BIN_FFMPEG)  else 'ffmpeg'
FFPROBE = _BIN_FFPROBE if _os.path.isfile(_BIN_FFPROBE) else 'ffprobe'

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
    Downloads original video from R2 public URL or local media.
    """
    if url.startswith('/media/'):
        # Legacy local file
        import os
        local_path = os.path.join(
            settings.MEDIA_ROOT,
            url.replace('/media/', '', 1)
        )
        shutil.copy2(local_path, destination)
    else:
        # R2 public URL — stream download
        import requests
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(destination, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)




def upload_hls_files(video_id, temp_dir):
    """Upload all HLS files to R2. Returns master_url and resolution URLs."""
    from videos.services import get_r2_client

    client   = get_r2_client()
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
                if filename.endswith('.m3u8'):
                    content_type = 'application/vnd.apple.mpegurl'
                elif filename.endswith('.ts'):
                    content_type = 'video/mp2t'
                elif filename.endswith('.vtt'):
                    content_type = 'text/vtt'
                else:
                    content_type = 'application/octet-stream'

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
        base = settings.R2_PUBLIC_URL
        master_url = f"{base}/videos/{video_id}/hls/master.m3u8"
        urls = {
            '360p':  f"{base}/videos/{video_id}/hls/360p/playlist.m3u8",
            '720p':  f"{base}/videos/{video_id}/hls/720p/playlist.m3u8",
            '1080p': f"{base}/videos/{video_id}/hls/1080p/playlist.m3u8",
        }

    return master_url, urls


def get_video_duration(input_path):
    """Uses FFPROBE to get video duration in seconds."""
    result = subprocess.run([
        FFPROBE, '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        input_path
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0


def get_audio_streams(input_path):
    """Returns list of audio streams with index, language, and title."""
    result = subprocess.run([
        FFPROBE, '-v', 'error',
        '-select_streams', 'a',
        '-show_entries', 'stream=index:stream_tags=language,title',
        '-of', 'json',
        input_path
    ], capture_output=True, text=True)
    try:
        return json.loads(result.stdout).get('streams', [])
    except (json.JSONDecodeError, KeyError):
        return []


def get_subtitle_streams(input_path):
    """
    Returns text-based subtitle streams only.
    Skips image-based subtitles (PGS, DVD) that cannot be converted to WebVTT.
    """
    TEXT_SUBTITLE_CODECS = {'subrip', 'ass', 'ssa', 'mov_text', 'webvtt', 'srt', 'text'}

    result = subprocess.run([
        FFPROBE, '-v', 'error',
        '-select_streams', 's',
        '-show_entries', 'stream=index,codec_name:stream_tags=language,title',
        '-of', 'json',
        input_path
    ], capture_output=True, text=True)
    try:
        streams = json.loads(result.stdout).get('streams', [])
        return [s for s in streams if s.get('codec_name', '') in TEXT_SUBTITLE_CODECS]
    except (json.JSONDecodeError, KeyError):
        return []


def _unique_lang_dir(lang_raw, lang_counts):
    """Returns a unique directory name for a language, handling duplicates."""
    lang = lang_raw.lower() or 'und'
    count = lang_counts.get(lang, 0)
    lang_counts[lang] = count + 1
    return lang if count == 0 else f"{lang}{count}"


def transcode_audio_renditions(input_path, output_dir, audio_streams):
    """
    Creates audio-only HLS renditions for each audio stream.
    Returns list of rendition dicts: {lang, name, lang_dir, is_default}
    """
    renditions = []
    lang_counts = {}

    for i, stream in enumerate(audio_streams):
        tags     = stream.get('tags', {})
        raw_lang = tags.get('language', '').strip()
        name     = tags.get('title', '').strip() or (raw_lang.upper() if raw_lang else f'Track {i + 1}')
        lang_dir = _unique_lang_dir(raw_lang or f'track{i}', lang_counts)

        audio_dir = os.path.join(output_dir, 'audio', lang_dir)
        os.makedirs(audio_dir, exist_ok=True)

        cmd = [
            FFMPEG, '-i', input_path,
            '-map', f'0:a:{i}',
            '-c:a', 'aac', '-b:a', '128k',
            '-f', 'hls',
            '-hls_time', '6',
            '-hls_playlist_type', 'vod',
            '-hls_segment_filename', os.path.join(audio_dir, 'segment%03d.ts'),
            os.path.join(audio_dir, 'playlist.m3u8'),
            '-y'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"Audio rendition failed for stream {i}: {result.stderr[-300:]}")
            shutil.rmtree(audio_dir, ignore_errors=True)
            continue

        renditions.append({
            'lang':     raw_lang or f'und{i}',
            'name':     name,
            'lang_dir': lang_dir,
            'is_default': i == 0,
        })
        logger.info(f"Audio rendition created: {name} ({raw_lang})")

    return renditions


def transcode_subtitle_renditions(input_path, output_dir, subtitle_streams, duration):
    """
    Extracts subtitle streams to WebVTT and wraps each in a single-segment
    HLS playlist (simplest approach compatible with hls.js).
    Returns list of rendition dicts: {lang, name, lang_dir, is_default}
    """
    renditions = []
    lang_counts = {}

    for i, stream in enumerate(subtitle_streams):
        tags     = stream.get('tags', {})
        raw_lang = tags.get('language', '').strip()
        name     = tags.get('title', '').strip() or (raw_lang.upper() if raw_lang else f'Sub {i + 1}')
        lang_dir = _unique_lang_dir(raw_lang or f'sub{i}', lang_counts)

        sub_dir  = os.path.join(output_dir, 'subtitles', lang_dir)
        os.makedirs(sub_dir, exist_ok=True)
        vtt_path = os.path.join(sub_dir, 'subtitle.vtt')

        cmd = [
            FFMPEG, '-i', input_path,
            '-map', f'0:s:{i}',
            '-c:s', 'webvtt',
            vtt_path, '-y'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"Subtitle extraction failed for stream {i}: {result.stderr[-300:]}")
            shutil.rmtree(sub_dir, ignore_errors=True)
            continue

        # Single-segment HLS subtitle playlist — hls.js loads the full VTT as one segment
        playlist = (
            '#EXTM3U\n'
            '#EXT-X-TARGETDURATION:99999\n'
            '#EXT-X-VERSION:3\n'
            f'#EXTINF:{duration:.3f},\n'
            'subtitle.vtt\n'
            '#EXT-X-ENDLIST\n'
        )
        with open(os.path.join(sub_dir, 'playlist.m3u8'), 'w') as f:
            f.write(playlist)

        renditions.append({
            'lang':     raw_lang or f'und{i}',
            'name':     name,
            'lang_dir': lang_dir,
            'is_default': False,
        })
        logger.info(f"Subtitle rendition created: {name} ({raw_lang})")

    return renditions


def build_master_playlist(output_dir, audio_renditions, subtitle_renditions, has_embedded_audio):
    """
    Builds master.m3u8 with:
    - #EXT-X-MEDIA entries for audio renditions (when multi-audio)
    - #EXT-X-MEDIA entries for subtitle renditions
    - #EXT-X-STREAM-INF for each video resolution
    """
    lines = ['#EXTM3U', '#EXT-X-VERSION:3', '']

    has_audio_group = bool(audio_renditions)
    has_sub_group   = bool(subtitle_renditions)

    # ── Audio rendition entries ────────────────────────────────
    if has_audio_group:
        for r in audio_renditions:
            lines.append(
                f'#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",'
                f'LANGUAGE="{r["lang"]}",'
                f'NAME="{r["name"]}",'
                f'DEFAULT={"YES" if r["is_default"] else "NO"},'
                f'AUTOSELECT=YES,'
                f'URI="audio/{r["lang_dir"]}/playlist.m3u8"'
            )
        lines.append('')

    # ── Subtitle rendition entries ─────────────────────────────
    if has_sub_group:
        for r in subtitle_renditions:
            lines.append(
                f'#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",'
                f'LANGUAGE="{r["lang"]}",'
                f'NAME="{r["name"]}",'
                f'DEFAULT={"YES" if r["is_default"] else "NO"},'
                f'AUTOSELECT=YES,'
                f'URI="subtitles/{r["lang_dir"]}/playlist.m3u8"'
            )
        lines.append('')

    # ── Video stream entries ───────────────────────────────────
    streams = [
        ('360p',  800_000,   '640x360'),
        ('720p',  2_500_000, '1280x720'),
        ('1080p', 5_000_000, '1920x1080'),
    ]

    for label, bandwidth, resolution in streams:
        attrs = [f'BANDWIDTH={bandwidth}', f'RESOLUTION={resolution}']
        if has_audio_group:
            attrs.append('AUDIO="audio"')
        if has_sub_group:
            attrs.append('SUBTITLES="subs"')
        lines.append(f'#EXT-X-STREAM-INF:{",".join(attrs)}')
        lines.append(f'{label}/playlist.m3u8')

    with open(os.path.join(output_dir, 'master.m3u8'), 'w') as f:
        f.write('\n'.join(lines) + '\n')

    logger.info("Master playlist created with audio/subtitle groups")


@shared_task(bind=True, max_retries=3)
def transcode_video(self, video_id):
    """
    Main Celery task:
    1. Download original video
    2. Probe audio and subtitle streams
    3. Transcode video resolutions (video-only for multi-audio, video+audio for single-audio)
    4. Create audio renditions (multi-audio only)
    5. Extract subtitle renditions (all text-based subtitle streams)
    6. Build master.m3u8 with proper #EXT-X-MEDIA groups
    7. Upload all files to storage
    8. Update Video model with URLs and status=ready
    """
    logger.info(f"Starting transcoding for video: {video_id}")

    try:
        video = Video.objects.get(id=video_id)
        logger.info(f"Video found: {video.title}")

        video.status   = 'processing'
        video.progress = 5
        video.stage    = 'Starting...'
        video.save()

        temp_dir   = tempfile.mkdtemp(prefix=f'transcode_{video_id}_')
        input_path = os.path.join(temp_dir, f'original.{video.format}')
        output_dir = os.path.join(temp_dir, 'hls')
        os.makedirs(output_dir, exist_ok=True)

        try:
            # ── Step 1: Download original ──────────────────────────
            logger.info("Downloading original video...")
            download_file(video.original_url, input_path)

            # ── Step 2: Get duration ───────────────────────────────
            duration = get_video_duration(input_path)
            video.duration = duration
            video.save()
            logger.info(f"Video duration: {duration}s")

            # ── Step 3: Probe audio & subtitle streams ─────────────
            audio_streams    = get_audio_streams(input_path)
            subtitle_streams = get_subtitle_streams(input_path)
            is_multi_audio   = len(audio_streams) > 1

            logger.info(
                f"Streams found: {len(audio_streams)} audio "
                f"({'multi' if is_multi_audio else 'single'}), "
                f"{len(subtitle_streams)} subtitle"
            )

            # ── Step 4: Transcode video resolutions ────────────────
            resolutions = [
                ('360p',  '640x360',   '800k'),
                ('720p',  '1280x720',  '2500k'),
                ('1080p', '1920x1080', '5000k'),
            ]

            for label, size, vbitrate in resolutions:
                res_dir = os.path.join(output_dir, label)
                os.makedirs(res_dir, exist_ok=True)

                cmd = [
                    FFMPEG, '-i', input_path,
                    '-map', '0:v:0',
                    '-vf', f'scale={size}',
                    '-c:v', 'libx264',
                    '-b:v', vbitrate,
                    '-preset', 'ultrafast',
                    '-threads', '1',
                ]

                if is_multi_audio:
                    # Video-only — audio comes from separate rendition playlists
                    cmd += ['-an']
                else:
                    # Embed the single audio track directly (simpler, no extra renditions)
                    cmd += ['-c:a', 'aac', '-b:a', '128k']

                cmd += [
                    '-f', 'hls',
                    '-hls_time', '6',
                    '-hls_playlist_type', 'vod',
                    '-hls_segment_filename', os.path.join(res_dir, 'segment%03d.ts'),
                    os.path.join(res_dir, 'playlist.m3u8'),
                    '-y'
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f'ffmpeg failed for {label}: {result.stderr[-500:]}')

                logger.info(f"Transcoded {label} successfully")
                # ✅ Update progress after each resolution
                _prog = {'360p': 25, '720p': 50, '1080p': 75}
                video.progress = _prog.get(label, video.progress)
                video.stage    = f'Transcoding {label}...'
                video.save(update_fields=['progress', 'stage'])

            # ── Step 5: Audio renditions (multi-audio only) ────────
            audio_renditions = []
            if is_multi_audio:
                audio_renditions = transcode_audio_renditions(
                    input_path, output_dir, audio_streams
                )

            # ── Step 6: Subtitle renditions ────────────────────────
            subtitle_renditions = transcode_subtitle_renditions(
                input_path, output_dir, subtitle_streams, duration
            )

            # ── Step 7: Build master.m3u8 ──────────────────────────
            build_master_playlist(
                output_dir,
                audio_renditions,
                subtitle_renditions,
                has_embedded_audio=not is_multi_audio,
            )

            # ── Step 8: Upload all HLS files to storage ────────────
            video.progress = 85
            video.stage    = 'Uploading to storage...'
            video.save(update_fields=['progress', 'stage'])
            logger.info("Uploading HLS files to storage...")
            master_url, resolution_urls = upload_hls_files(video_id, output_dir)

            # ── Step 9: Update Video model ─────────────────────────
            video.master_url = master_url
            video.url_360p   = resolution_urls['360p']
            video.url_720p   = resolution_urls['720p']
            video.url_1080p  = resolution_urls['1080p']
            video.status   = 'ready'
            video.progress = 100
            video.stage    = 'Complete'
            video.save()

            logger.info(f"Transcoding complete for video: {video_id}")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info("Temp files cleaned up")

    except Video.DoesNotExist:
        logger.error(f"Video not found in DB: {video_id}")

    except Exception as exc:
        logger.error(f"Transcoding failed: {exc}", exc_info=True)
        try:
            video = Video.objects.get(id=video_id)
            video.status   = 'failed'
            video.progress = 0
            video.stage    = 'Failed'
            video.save()
        except Exception:
            pass
        # ✅ Only retry if running as a real Celery task (has request context)
        if hasattr(self, 'request') and self.request.id:
            raise self.retry(exc=exc, countdown=60)
        
    
def transcode_video_sync(video_id):
    logger.info(f"[Sync] Starting transcode for video: {video_id}")
    try:
        transcode_video.run(video_id)  # ✅ .run() already binds self
    except Exception as exc:
        logger.error(f"[Sync] Transcode failed for {video_id}: {exc}", exc_info=True)
        
