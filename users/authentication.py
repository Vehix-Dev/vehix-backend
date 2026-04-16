from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

class SingleDeviceJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication that verifies the login_id stored in the token
    matches the current_login_id in the database.
    """
    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)

        # Check if single device login is enforced
        if hasattr(user, 'current_login_id') and user.current_login_id:
            token_login_id = validated_token.get('login_id')
            
            if not token_login_id or str(user.current_login_id) != str(token_login_id):
                # This session has been invalidated by a newer login
                raise AuthenticationFailed(
                    'Your session has expired because you logged in from another device.',
                    code='session_invalidated'
                )

        return user, validated_token
