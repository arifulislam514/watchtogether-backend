#!/usr/bin/env bash
set -o errexit

echo "==> Downloading ffmpeg for Railway..."
FFMPEG_DIR="./bin"
mkdir -p "$FFMPEG_DIR"

curl -L https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz \
  -o /tmp/ffmpeg.tar.xz
tar -xf /tmp/ffmpeg.tar.xz -C /tmp
cp /tmp/ffmpeg-master-latest-linux64-gpl/bin/ffmpeg  "$FFMPEG_DIR/ffmpeg"
cp /tmp/ffmpeg-master-latest-linux64-gpl/bin/ffprobe "$FFMPEG_DIR/ffprobe"
chmod +x "$FFMPEG_DIR/ffmpeg" "$FFMPEG_DIR/ffprobe"
rm -rf /tmp/ffmpeg.tar.xz /tmp/ffmpeg-master-latest-linux64-gpl

echo "==> FFmpeg ready:"
"$FFMPEG_DIR/ffmpeg" -version | head -1
