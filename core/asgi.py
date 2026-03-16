# core/asgi.py
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.middleware import BaseMiddleware
from django.conf import settings
from core.middleware import JWTAuthMiddleware
import rooms.routing


class CORSOriginValidator(BaseMiddleware):
    """
    Validates WebSocket origin against CORS_ALLOWED_ORIGINS.
    Replaces AllowedHostsOriginValidator which only checks ALLOWED_HOSTS
    (backend domain) — not the frontend domain.
    """
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            headers = dict(scope.get('headers', []))
            origin  = headers.get(b'origin', b'').decode()

            allowed = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
            allow_all = getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False)

            if not allow_all and origin and origin not in allowed:
                await send({'type': 'websocket.close', 'code': 4403})
                return

        return await super().__call__(scope, receive, send)


application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': CORSOriginValidator(
        JWTAuthMiddleware(
            URLRouter(rooms.routing.websocket_urlpatterns)
        )
    ),
})
