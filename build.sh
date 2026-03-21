#!/usr/bin/env bash
set -o errexit

echo "==> Installing Python packages..."
pip install -r requirements.txt

echo "==> Downloading static ffmpeg binary..."
# Download pre-built static ffmpeg binary (no apt-get needed)
mkdir -p /opt/ffmpeg
curl -L https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz \
  -o /tmp/ffmpeg.tar.xz
tar -xf /tmp/ffmpeg.tar.xz -C /tmp
cp /tmp/ffmpeg-master-latest-linux64-gpl/bin/ffmpeg  /opt/ffmpeg/ffmpeg
cp /tmp/ffmpeg-master-latest-linux64-gpl/bin/ffprobe /opt/ffmpeg/ffprobe
chmod +x /opt/ffmpeg/ffmpeg /opt/ffmpeg/ffprobe
rm -rf /tmp/ffmpeg.tar.xz /tmp/ffmpeg-master-latest-linux64-gpl

echo "==> Verifying ffmpeg..."
/opt/ffmpeg/ffmpeg  -version | head -1
/opt/ffmpeg/ffprobe -version | head -1

echo "==> Collecting static files..."
python manage.py collectstatic --no-input

echo "==> Running migrations..."
python manage.py migrate

echo "==> Build complete!"