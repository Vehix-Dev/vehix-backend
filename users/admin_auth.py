from .tokens import CustomTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
import uuid
from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed


class AdminTokenObtainPairSerializer(CustomTokenObtainPairSerializer):
    def validate(self, attrs):
        username_field = self.username_field
        username = attrs.get(username_field)
        if username and '@' in username:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                u = User.objects.get(email__iexact=username)
                attrs[username_field] = getattr(u, username_field)
            except User.DoesNotExist:
                pass

        # Since we inherit from CustomTokenObtainPairSerializer, 
        # but we handle credentials differently here (super.validate calls authenticate),
        # we should ensure the user is authenticated and then update their login_id.
        
        from django.contrib.auth import authenticate
        # We need to manually authenticate here because we might have changed the username to email
        user = authenticate(username=attrs.get(username_field), password=attrs.get('password'))
        if user and user.is_active:
            new_login_id = uuid.uuid4()
            user.current_login_id = new_login_id
            user.save(update_fields=['current_login_id'])
            self.user = user

        data = super().validate(attrs)
        user = getattr(self, 'user', None)
        if not user or not (getattr(user, 'role', None) == 'ADMIN' or getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)):
            raise AuthenticationFailed('User is not an admin')
        
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': getattr(user, 'role', 'ADMIN'),
            'is_approved': getattr(user, 'is_approved', False),
        }
        return data


class AdminTokenObtainPairView(TokenObtainPairView):
    serializer_class = AdminTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except AuthenticationFailed:
            return Response({'detail': 'Invalid credentials or not an admin'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)
