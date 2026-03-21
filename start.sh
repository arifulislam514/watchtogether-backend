#!/usr/bin/env bash
set -o errexit

echo "==> Starting Celery worker..."
# ✅ Redirect stdout+stderr to Render's log capture
celery -A core worker --loglevel=info --concurrency=1 2>&1 &
CELERY_PID=$!
echo "==> Celery PID: $CELERY_PID"

echo "==> Starting Daphne..."
daphne -b 0.0.0.0 -p $PORT core.asgi:application
