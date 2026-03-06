from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import UntypedToken
from django.contrib.auth import get_user_model
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from jwt import decode as jwt_decode
from django.conf import settings

User = get_user_model()

@database_sync_to_async
def get_user(user_id, token_login_id=None):
    try:
        user = User.objects.get(id=user_id)
        # Single-device enforcement: check login_id matches
        if token_login_id:
            db_login_id = str(user.current_login_id) if user.current_login_id else None
            if db_login_id != str(token_login_id):
                print(f"WS Auth: Session invalid for user {user_id} - token_login_id={token_login_id}, db_login_id={db_login_id}")
                return AnonymousUser()
        return user
    except User.DoesNotExist:
        return AnonymousUser()

class JwtAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token = params.get("token", [None])[0]

        scope["user"] = AnonymousUser()

        if token:
            try:
                UntypedToken(token)
                payload = jwt_decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                user_id = payload.get("user_id")
                login_id = payload.get("login_id")
                if user_id:
                    scope["user"] = await get_user(user_id, login_id)
            except Exception:
                pass

        return await super().__call__(scope, receive, send)
