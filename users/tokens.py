from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from datetime import timedelta
from django.contrib.auth import authenticate
from rest_framework import serializers
import uuid

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['login_id'] = str(user.current_login_id)
        return token

    def validate(self, attrs):
        username = attrs.get(self.username_field)
        password = attrs.get('password')
        print(f"DEBUG AUTH: Attempting login for username/phone: '{username}'", flush=True)

        # Try to resolve username from phone number if username not found
        if username:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            # Check if user exists with this username
            if not User.objects.filter(username=username).exists():
                print(f"DEBUG AUTH: Username '{username}' not found. Trying lookup by phone.", flush=True)
                try:
                    user_obj = User.objects.get(phone=username)
                    print(f"DEBUG AUTH: Found user {user_obj.username} by phone {username}", flush=True)
                    attrs[self.username_field] = user_obj.username
                except User.DoesNotExist:
                    print(f"DEBUG AUTH: No user found with phone '{username}'", flush=True)
                    pass
            else:
                 print(f"DEBUG AUTH: User found by exact username '{username}'", flush=True)

        try:
            data = super().validate(attrs)
            print("DEBUG AUTH: Authentication successful.", flush=True)
        except Exception as e:
            print(f"DEBUG AUTH: Authentication FAILED. Error: {e}", flush=True)
            raise e
        
        if self.user.role in ['RIDER', 'RODIE']:
            refresh = self.get_token(self.user)
            long_life = timedelta(days=365*50)
            refresh.set_exp(lifetime=long_life)
            access = refresh.access_token
            access.set_exp(lifetime=long_life)
            data["refresh"] = str(refresh)
            data["access"] = str(access)
            
        return data

class RiderTokenObtainPairSerializer(CustomTokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user.role != 'RIDER':
            raise serializers.ValidationError('This account is not a Rider account.')
        return data

class RoadieTokenObtainPairSerializer(CustomTokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        print(f"DEBUG ROADIE LOGIN: User role is {self.user.role}", flush=True)
        if self.user.role != 'RODIE':
            print(f"DEBUG ROADIE LOGIN: Role mismatch! Expected RODIE, got {self.user.role}", flush=True)
            raise serializers.ValidationError('This account is not a Roadie account.')
        return data

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class RiderLoginView(TokenObtainPairView):
    serializer_class = RiderTokenObtainPairSerializer

class RoadieLoginView(TokenObtainPairView):
    serializer_class = RoadieTokenObtainPairSerializer
