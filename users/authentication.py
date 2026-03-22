from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import exceptions

class CustomJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        
        if user is None:
            return None
            
        token_login_id = validated_token.get('login_id')
        
        print(f"🔍 AUTH DEBUG: User {user.username}, token_login_id: {token_login_id}, user.current_login_id: {user.current_login_id}")
        
        # Handle users with NULL current_login_id (legacy accounts)
        if user.current_login_id is None:
            import uuid
            print(f"🔍 AUTH DEBUG: Setting current_login_id for user {user.username}")
            user.current_login_id = uuid.uuid4()
            user.save(update_fields=['current_login_id'])
            return user
            
        # If the token doesn't have a login_id, or it doesn't match the current one in DB,
        # fail authentication (unless it's an admin and we decide to exempt them - but plan says all users).
        if not token_login_id or str(user.current_login_id) != str(token_login_id):
            print(f"🔍 AUTH DEBUG: AUTHENTICATION FAILED - login_id mismatch!")
            print(f"🔍 AUTH DEBUG: Token login_id: {token_login_id} (type: {type(token_login_id)})")
            print(f"🔍 AUTH DEBUG: User current_login_id: {user.current_login_id} (type: {type(user.current_login_id)})")
            raise exceptions.AuthenticationFailed(
                'This session is no longer valid. Another device has logged in.',
                code='multiple_device_login'
            )
            
        print(f"🔍 AUTH DEBUG: Authentication successful for user {user.username}")
        return user
