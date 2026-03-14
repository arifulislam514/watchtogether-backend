# core/asgi.py
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from core.middleware import JWTAuthMiddleware
import rooms.routing

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': JWTAuthMiddleware(
            URLRouter(rooms.routing.websocket_urlpatterns)
    ),
})

