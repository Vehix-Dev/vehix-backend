from .tokens import CustomTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
import uuid
from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed


class AdminTokenObtainPairSerializer(CustomTokenObtainPairSerializer):
    def validate(self, attrs):
        # The field name in attrs is now 'username' due to __init__ in parent
        username = attrs.get('username')
        password = attrs.get('password')
        
        # Call parent's validate first to handle multi-field lookup (email/phone/username) 
        # and identifier resolution (setting attrs[self.username_field] = external_id)
        # Note: We need to put external_id into attrs for the base authenticate() to work.
        data = super().validate(attrs)
        
        user = self.user
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
