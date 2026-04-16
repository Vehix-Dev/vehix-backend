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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The base class automatically adds a field named after USERNAME_FIELD (external_id).
        # We want the client to send 'username' (which could be email/phone/username).
        if self.username_field in self.fields:
            self.fields['username'] = self.fields.pop(self.username_field)

    def validate(self, attrs):
        # The client sends 'username', but we must identify the user and
        # provide the 'external_id' (which is our USERNAME_FIELD) to the
        # base class's authentication logic.
        username = attrs.get('username')
        password = attrs.get('password')
        
        # Determine target role if we are in a subclass
        target_role = getattr(self, 'target_role', None)
        
        print(f"DEBUG AUTH: Attempting login for username/email/phone: '{username}' (Target Role: {target_role})", flush=True)

        if username:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Use role in filter if target_role is set
            role_filter = {'role': target_role} if target_role else {}
            
            # 1. Try exact username match
            user_obj = User.objects.filter(username=username, **role_filter).first()
            
            if not user_obj:
                # 2. Try email match
                user_obj = User.objects.filter(email__iexact=username, **role_filter).first()
            
            if not user_obj:
                # 3. Try phone match
                user_obj = User.objects.filter(phone=username, **role_filter).first()

            if user_obj:
                print(f"DEBUG AUTH: Found user {user_obj.username} (ExtID: {user_obj.external_id}, Role: {user_obj.role}, Active: {user_obj.is_active})", flush=True)
                
                # Check password manually for debugging
                pw_match = user_obj.check_password(password)
                print(f"DEBUG AUTH: Password match test: {pw_match}", flush=True)
                
                # Set the key that TokenObtainPairSerializer expects (self.username_field)
                attrs[self.username_field] = user_obj.external_id
                
                # CRITICAL: Remove 'username' from attrs to avoid conflict with authenticate() arguments
                if 'username' in attrs and 'username' != self.username_field:
                    attrs.pop('username')
            else:
                print(f"DEBUG AUTH: No user found for input '{username}' with role '{target_role}'", flush=True)
                # Ensure the expected field is present for super().validate()
                attrs[self.username_field] = username 

        try:
            print(f"DEBUG AUTH: Calling super().validate with attrs keys: {list(attrs.keys())}", flush=True)
            data = super().validate(attrs)
            print("DEBUG AUTH: super().validate SUCCEEDED.", flush=True)
        except Exception as e:
            print(f"DEBUG AUTH: super().validate FAILED. Error: {e}", flush=True)
            # If it failed but our manual check worked, there's a backend/simplejwt config issue
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
