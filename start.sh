#!/usr/bin/env bash
set -o errexit

# Start Celery worker in background
celery -A core worker --loglevel=info --concurrency=1 &

# Start Daphne in foreground
daphne -b 0.0.0.0 -p $PORT core.asgi:application
