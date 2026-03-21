#!/usr/bin/env bash
set -o errexit

echo "==> Installing Python packages..."
pip install -r requirements.txt

echo "==> Downloading static ffmpeg binary..."
# Download into the project's own bin/ directory
# This is ALWAYS preserved between build and runtime on Render
mkdir -p bin
curl -L https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz \
  -o /tmp/ffmpeg.tar.xz
tar -xf /tmp/ffmpeg.tar.xz -C /tmp
cp /tmp/ffmpeg-master-latest-linux64-gpl/bin/ffmpeg  bin/ffmpeg
cp /tmp/ffmpeg-master-latest-linux64-gpl/bin/ffprobe bin/ffprobe
chmod +x bin/ffmpeg bin/ffprobe
rm -rf /tmp/ffmpeg.tar.xz /tmp/ffmpeg-master-latest-linux64-gpl

echo "==> Verifying ffmpeg..."
./bin/ffmpeg  -version | head -1
./bin/ffprobe -version | head -1

echo "==> Collecting static files..."
python manage.py collectstatic --no-input

echo "==> Running migrations..."
python manage.py migrate

echo "==> Build complete!"
