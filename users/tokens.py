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
        
        # Determine target role if we are in a subclass
        target_role = getattr(self, 'target_role', None)
        
        print(f"DEBUG AUTH: Attempting login for username/email/phone: '{username}' (Target Role: {target_role})", flush=True)

        if username:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Use role in filter if target_role is set
            role_filter = {'role': target_role} if target_role else {}
            
            # Check if user exists with this username + role
            user_query = User.objects.filter(username=username, **role_filter)
            
            if not user_query.exists():
                print(f"DEBUG AUTH: No match for exact username '{username}' with role '{target_role}'. Trying lookup by email and phone.", flush=True)
                try:
                    # First try email lookup + role
                    user_obj = User.objects.filter(email__iexact=username, **role_filter).first()
                    if user_obj:
                        print(f"DEBUG AUTH: Found user {user_obj.username} by email {username} with role {user_obj.role}", flush=True)
                        attrs[self.username_field] = user_obj.username
                    else:
                        print(f"DEBUG AUTH: No user found with email '{username}' and role '{target_role}'. Trying phone lookup.", flush=True)
                        # Then try phone lookup + role
                        user_obj = User.objects.filter(phone=username, **role_filter).first()
                        if user_obj:
                            print(f"DEBUG AUTH: Found user {user_obj.username} by phone {username} with role {user_obj.role}", flush=True)
                            attrs[self.username_field] = user_obj.username
                        else:
                            print(f"DEBUG AUTH: No user found with phone '{username}' and role '{target_role}'", flush=True)
                except Exception as e:
                    print(f"DEBUG AUTH Error during lookup: {e}")
            else:
                 user_obj = user_query.first()
                 print(f"DEBUG AUTH: User found by exact username '{username}' and role '{user_obj.role}'", flush=True)
                 attrs[self.username_field] = user_obj.username

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
            'services_selected': getattr(self.user, 'services_selected', False),
            'is_approved': getattr(self.user, 'is_approved', False),
        }
            
        return data

class RiderTokenObtainPairSerializer(CustomTokenObtainPairSerializer):
    target_role = 'RIDER'
    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user.role != 'RIDER':
            raise serializers.ValidationError('This account is not a Rider account.')
        return data

class RoadieTokenObtainPairSerializer(CustomTokenObtainPairSerializer):
    target_role = 'RODIE'
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
