from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.tokens import AccessToken
from django.db import close_old_connections
from django.contrib.auth import get_user_model
from urllib.parse import parse_qs

User = get_user_model()

@database_sync_to_async
def get_user(token_key):
    try:
        access_token = AccessToken(token_key)
        user_id = access_token['user_id']
        user = User.objects.get(id=user_id)
        
        # Check if token's login_id matches user's current login session
        token_login_id = access_token.get('login_id')
        db_login_id = str(user.current_login_id) if user.current_login_id else None
        
        if not token_login_id or db_login_id != str(token_login_id):
            print(f"WS Auth Error: Session invalid for user {user_id} - token_login_id={token_login_id}, db_login_id={db_login_id}")
            return AnonymousUser()
        
        print(f"WS Auth OK: user {user_id} ({user.role})")
        return user
    except Exception as e:
        print(f"WS Auth Error: {e}")
        return AnonymousUser()

class JwtAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        close_old_connections()
        try:
            query_string = scope.get('query_string', b'').decode()
            query_params = parse_qs(query_string)
            token = query_params.get('token', [None])[0]
            
            if token:
                scope['user'] = await get_user(token)
            else:
                scope['user'] = AnonymousUser()
        except Exception as e:
            print(f"Middleware Error: {e}")
            scope['user'] = AnonymousUser()
            
        return await super().__call__(scope, receive, send)
