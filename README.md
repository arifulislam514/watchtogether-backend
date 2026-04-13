# WatchTogether — Backend

A Django-based backend for WatchTogether, a real-time synchronized video-watching platform. Handles REST API, WebSocket room management, HLS video transcoding, and direct cloud storage.

**Live API:** https://watchtogether-backend-jw7b.onrender.com

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 5.2 + Django REST Framework |
| WebSocket | Django Channels 4 + Daphne |
| Task Queue | Celery 5 + Redis |
| Database | PostgreSQL (Supabase) |
| Storage | Cloudflare R2 (S3-compatible) |
| Transcoding | FFmpeg (HLS pipeline) |
| Auth | Djoser + SimpleJWT |
| Deployment | Render (API) + Railway (Celery worker) |

---

## Architecture

```
Browser
  │
  ├── HTTP  → Render (Django + Daphne)
  │               │
  │               ├── REST API  → Supabase PostgreSQL
  │               ├── WebSocket → Redis (channels layer)
  │               └── Presigned URL → Cloudflare R2 (direct upload)
  │
  └── R2 Direct Upload (browser → R2, bypasses server)
          │
          └── confirm-upload → Railway (Celery worker)
                                    │
                                    └── FFmpeg transcoding → R2 (HLS output)
```

---

## Project Structure

```
watchtogether-backend/
├── core/
│   ├── settings.py       # All configuration via django-decouple
│   ├── asgi.py           # Daphne + Channels routing
│   ├── middleware.py     # JWT WebSocket auth (?token= query param)
│   └── urls.py
├── users/
│   ├── models.py         # Custom AbstractUser (email login, UUID pk)
│   └── views.py          # Profile, admin endpoints
├── rooms/
│   ├── models.py         # Room, RoomMember, Message
│   ├── consumers.py      # WebSocket consumer — all room events
│   └── views.py          # Room CRUD, join/leave, member management
├── videos/
│   ├── models.py         # Video model with progress/stage/qualities
│   ├── views.py          # Presigned upload, confirm, CRUD
│   ├── tasks.py          # Celery transcoding task (FFmpeg HLS pipeline)
│   ├── serializers.py
│   └── migrations/
├── build.sh              # Render build — installs deps + FFmpeg + migrate
├── build_worker.sh       # Railway build — installs FFmpeg for Celery worker
└── start.sh              # Render start — runs Daphne
```

---

## Apps

### `users`
Custom user model using email as the login field. Supports admin flag and ban status. Auth handled by Djoser (register, login, JWT refresh).

### `rooms`
Rooms have a host, password protection, max member limit, and an optional selected video. Members have a ready state — playback auto-starts when all members are ready.

### `videos`
Videos are uploaded directly to Cloudflare R2 via presigned URLs (bypasses Render, supports files up to 4GB). After upload, a Celery task on Railway runs FFmpeg to produce HLS streams in selected resolutions.

---

## WebSocket Events

All events flow through `rooms/consumers.py` via Django Channels.

| Event | Direction | Description |
|---|---|---|
| `PLAY` | broadcast | Resume playback at timestamp |
| `PAUSE` | broadcast | Pause playback at timestamp |
| `SEEK` | broadcast | Jump to timestamp |
| `READY` | broadcast | Member toggles ready state |
| `CHAT` | broadcast | Chat message |
| `SYNC_TIME` | broadcast | Periodic drift correction (every 2s) |
| `SYNC_STATE` | broadcast | Full state sync for new joiners |
| `NETWORK_WAIT` | broadcast | Member is buffering |
| `NETWORK_RESUME` | broadcast | Member finished buffering |
| `VIDEO_SELECTED` | broadcast | Host changed the video |
| `MEMBER_JOINED` | broadcast | New member connected |
| `MEMBER_LEFT` | broadcast | Member left gracefully |
| `MEMBER_DISCONNECTED` | broadcast | Member lost connection |
| `VOICE_JOIN` | broadcast | Member joined voice call |
| `VOICE_LEAVE` | broadcast | Member left voice call |
| `WEBRTC_OFFER` | targeted | WebRTC peer offer |
| `WEBRTC_ANSWER` | targeted | WebRTC peer answer |
| `WEBRTC_ICE` | targeted | ICE candidate exchange |

---

## HLS Transcoding Pipeline

1. Browser uploads original file directly to R2 (presigned PUT URL)
2. Browser calls `POST /api/videos/{id}/confirm-upload/`
3. Celery task on Railway picks it up
4. FFmpeg downloads from R2, transcodes to HLS:
   - Probes audio streams — multi-audio gets separate `#EXT-X-MEDIA` renditions
   - Probes subtitle streams — text-based subs (SRT/ASS/VTT) extracted to WebVTT
   - Transcodes selected resolutions: 360p / 480p / 720p / 1080p
   - Builds `master.m3u8` with audio + subtitle groups
5. Uploads all HLS files back to R2
6. Updates Video model (`status=ready`, `master_url`, resolution URLs)

---

## API Endpoints

```
Auth
  POST   /api/auth/users/           Register
  POST   /api/auth/jwt/create/      Login (returns access + refresh tokens)
  POST   /api/auth/jwt/refresh/     Refresh token

Users
  GET    /api/users/me/             Current user profile
  PATCH  /api/users/me/             Update profile

Videos
  GET    /api/videos/               List my videos
  POST   /api/videos/presigned-upload/   Request presigned R2 URL
  POST   /api/videos/{id}/confirm-upload/ Trigger transcoding after upload
  GET    /api/videos/{id}/          Video detail
  DELETE /api/videos/{id}/          Delete video + R2 files

Rooms
  GET    /api/rooms/                List rooms
  POST   /api/rooms/                Create room
  GET    /api/rooms/{id}/           Room detail
  PATCH  /api/rooms/{id}/           Update room (host only)
  DELETE /api/rooms/{id}/           Close room (host only)
  POST   /api/rooms/{id}/join/      Join room
  POST   /api/rooms/{id}/leave/     Leave room
  DELETE /api/rooms/{id}/members/{user_id}/  Remove member (host only)

Admin
  GET    /api/admin/users/          List all users
  POST   /api/admin/users/{id}/ban/ Ban user
  GET    /api/admin/videos/         List all videos
  DELETE /api/admin/videos/{id}/    Delete any video

WebSocket
  WS     /ws/rooms/{room_id}/?token={jwt}
```

---

## Local Development

### Requirements
- Python 3.11+
- FFmpeg installed and on PATH
- Redis running locally (or Memurai on Windows)
- PostgreSQL database

### Setup

```bash
git clone https://github.com/arifulislam514/watchtogether-backend
cd watchtogether-backend

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Create `.env` in the project root:

```env
SECRET_KEY=your-secret-key
DEBUG=True

DB_NAME=watchtogether
DB_USER=postgres
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=5432

REDIS_URL=redis://localhost:6379

R2_ACCESS_KEY_ID=your-key
R2_SECRET_ACCESS_KEY=your-secret
R2_BUCKET_NAME=watch-together-videos
R2_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com
R2_PUBLIC_URL=https://pub-xxxx.r2.dev
```

Run migrations and start:

```bash
python manage.py migrate
python manage.py createsuperuser
daphne -b 0.0.0.0 -p 8000 core.asgi:application
```

In a separate terminal, start Celery:

```bash
celery -A core worker --loglevel=info --concurrency=2
```

---

## Deployment

### Render (API Server)

- **Build Command:** `./build.sh`
- **Start Command:** `./start.sh` (runs Daphne)
- Build script downloads static FFmpeg binary to `./bin/` and runs migrations

### Railway (Celery Worker)

- **Build Command:** `pip install -r requirements.txt && ./build_worker.sh`
- **Start Command:** `celery -A core worker --loglevel=info --concurrency=2`
- Uses Railway Redis public URL as broker

### Required Environment Variables (both services)

```
SECRET_KEY
DEBUG=False
ALLOWED_HOSTS
DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
REDIS_URL
R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
R2_BUCKET_NAME, R2_ENDPOINT_URL, R2_PUBLIC_URL
CORS_ALLOWED_ORIGINS
```

---

## Author

**Ariful Islam** — [GitHub](https://github.com/arifulislam514) · [Portfolio](https://ariful-islam-iota.vercel.app)
