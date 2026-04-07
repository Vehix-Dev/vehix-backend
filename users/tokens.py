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
        print(f"DEBUG AUTH: Attempting login for username/email/phone: '{username}'", flush=True)

        # Try to resolve username from email or phone if username not found
        if username:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            # Check if user exists with this username
            if not User.objects.filter(username=username).exists():
                print(f"DEBUG AUTH: Username '{username}' not found. Trying lookup by email and phone.", flush=True)
                try:
                    # First try email lookup
                    user_obj = User.objects.filter(email__iexact=username).first()
                    if user_obj:
                        print(f"DEBUG AUTH: Found user {user_obj.username} by email {username}", flush=True)
                        attrs[self.username_field] = user_obj.username
                    else:
                        print(f"DEBUG AUTH: No user found with email '{username}'. Trying phone lookup.", flush=True)
                        # Then try phone lookup
                        user_obj = User.objects.filter(phone=username).first()
                        if user_obj:
                            print(f"DEBUG AUTH: Found user {user_obj.username} by phone {username}", flush=True)
                            attrs[self.username_field] = user_obj.username
                        else:
                            print(f"DEBUG AUTH: No user found with phone '{username}'", flush=True)
                except Exception as e:
                    print(f"DEBUG AUTH Error during lookup: {e}")
            else:
                 print(f"DEBUG AUTH: User found by exact username '{username}'", flush=True)

        try:
            data = super().validate(attrs)
            print("DEBUG AUTH: Authentication successful.", flush=True)
        except Exception as e:
            print(f"DEBUG AUTH: Authentication FAILED. Error: {e}", flush=True)
            raise e
        
        # Generate new login_id to invalidate previous sessions for all user roles
        new_login_id = uuid.uuid4()
        self.user.current_login_id = new_login_id
        self.user.save(update_fields=['current_login_id'])
        print(f"DEBUG AUTH: Generated new login_id for {self.user.username} ({self.user.role}): {new_login_id}", flush=True)
        
        refresh = self.get_token(self.user)
        long_life = timedelta(days=365*50)
        refresh.set_exp(lifetime=long_life)
        access = refresh.access_token
        access.set_exp(lifetime=long_life)
        data["refresh"] = str(refresh)
        data["access"] = str(access)
        
        # Include user details in response
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'phone': self.user.phone,
            'role': self.user.role,
            'external_id': self.user.external_id,
            'services_selected': self.user.services_selected,
            'is_approved': self.user.is_approved,
        }
            
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
