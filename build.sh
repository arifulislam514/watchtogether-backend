#!/usr/bin/env bash
set -o errexit

echo "==> Installing system packages..."
apt-get update -qq
apt-get install -y -qq ffmpeg

echo "==> Verifying ffmpeg..."
ffmpeg -version | head -1
ffprobe -version | head -1

echo "==> Installing Python packages..."
pip install -r requirements.txt

echo "==> Collecting static files..."
python manage.py collectstatic --no-input

echo "==> Running migrations..."
python manage.py migrate

echo "==> Build complete!"