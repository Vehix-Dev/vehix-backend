from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import exceptions

class CustomJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        
        if user is None:
            return None
            
        token_login_id = validated_token.get('login_id')
        
        # If the token doesn't have a login_id, or it doesn't match the current one in DB,
        # fail authentication (unless it's an admin and we decide to exempt them - but plan says all users).
        if not token_login_id or str(user.current_login_id) != str(token_login_id):
            raise exceptions.AuthenticationFailed(
                'This session is no longer valid. Another device has logged in.',
                code='multiple_device_login'
            )
            
        return user
