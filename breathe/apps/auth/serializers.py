"""
Chunk 2.3: Multi-Tenancy Isolation - Auth Serializers

LoginSerializer: Validates username/password, returns JWT tokens
UserProfileSerializer: Returns user info including tenant_id
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from breathe.apps.tenants.models import Tenant
from .models import UserProfile


class TenantSerializer(serializers.ModelSerializer):
    """Minimal tenant info for client display"""

    class Meta:
        model = Tenant
        fields = ['id', 'name', 'slug', 'plan']


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for UserProfile.

    Includes username (from User), tenant info, role, and tenant_id.
    Used after login to return user context.
    """
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    tenant = TenantSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email', 'tenant', 'role', 'is_active', 'created_at']


class LoginSerializer(serializers.Serializer):
    """
    Login endpoint serializer.

    Input: username, password
    Output: access token, refresh token, user profile

    Why separate from TokenObtainPairSerializer:
    - Custom response includes UserProfile data (tenant, role)
    - Standard simplejwt response is minimal (just tokens)
    """
    username = serializers.CharField(max_length=255, required=True)
    password = serializers.CharField(max_length=255, write_only=True, required=True)

    def validate(self, attrs):
        """
        Validate username/password and return tokens + user profile.
        """
        from django.contrib.auth import authenticate

        username = attrs.get('username')
        password = attrs.get('password')

        # Authenticate user
        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid username or password")

        # Check if user has a profile (multi-tenancy requirement)
        try:
            profile = user.profile
        except UserProfile.DoesNotExist:
            raise serializers.ValidationError("User is not associated with any tenant")

        # Check if user is active
        if not profile.is_active:
            raise serializers.ValidationError("User account is disabled")

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        # Embed tenant_id in token claims (useful for frontend)
        refresh['tenant_id'] = str(profile.tenant_id)
        refresh['role'] = profile.role

        attrs['user'] = user
        attrs['profile'] = profile
        attrs['refresh'] = str(refresh)
        attrs['access'] = str(refresh.access_token)

        return attrs

    def to_representation(self, instance):
        """
        Custom response format.
        """
        return {
            'access': instance['access'],
            'refresh': instance['refresh'],
            'user': UserProfileSerializer(instance['profile']).data
        }


class UserSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for User model.
    Used in audit logs and approval history.
    """

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class TokenRefreshResponseSerializer(serializers.Serializer):
    """
    Response after refreshing access token.
    """
    access = serializers.CharField()
    refresh = serializers.CharField()
