# core/middleware.py
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.conf import settings
from users.models import User


@database_sync_to_async
def get_user_from_token(token_string):
    try:
        token = AccessToken(token_string)
        user_id = token['user_id']
        return User.objects.get(id=user_id)
    except (InvalidToken, TokenError, User.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Reads JWT token from WebSocket query string.
    Frontend connects like: ws://localhost:8000/ws/rooms/{id}/?token=<access_token>
    """
    async def __call__(self, scope, receive, send):
        # Parse query string for token
        from urllib.parse import parse_qs
        query_string = scope.get('query_string', b'').decode()
        params = parse_qs(query_string)
        token_list = params.get('token', [None])
        token_string = token_list[0] if token_list else None

        if token_string:
            scope['user'] = await get_user_from_token(token_string)
        else:
            scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)
    
