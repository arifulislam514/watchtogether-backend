#!/usr/bin/env bash
set -o errexit

echo "==> Starting Daphne (transcoding runs in background threads)..."
daphne -b 0.0.0.0 -p $PORT core.asgi:application