"""Auth serializers: login, user profile, token refresh."""

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
    """Validates credentials and returns JWT tokens + user profile."""
    username = serializers.CharField(max_length=255, required=True)
    password = serializers.CharField(max_length=255, write_only=True, required=True)

    def validate(self, attrs):
        from django.contrib.auth import authenticate

        username = attrs.get('username')
        password = attrs.get('password')

        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid username or password")

        try:
            profile = user.profile
        except UserProfile.DoesNotExist:
            raise serializers.ValidationError("User is not associated with any tenant")

        if not profile.is_active:
            raise serializers.ValidationError("User account is disabled")

        refresh = RefreshToken.for_user(user)
        refresh['tenant_id'] = str(profile.tenant_id)
        refresh['role'] = profile.role

        attrs['user'] = user
        attrs['profile'] = profile
        attrs['refresh'] = str(refresh)
        attrs['access'] = str(refresh.access_token)

        return attrs

    def to_representation(self, instance):
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
