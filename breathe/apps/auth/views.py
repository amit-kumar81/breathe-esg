"""
Chunk 2.3: Multi-Tenancy Isolation - Auth Views

Login, Logout, and Token Refresh endpoints.

JWT flow:
1. POST /api/auth/login/ with username + password
2. Returns access_token (15 min), refresh_token (7 days)
3. Frontend stores tokens, sends access_token in Authorization header
4. If access_token expires, POST /api/auth/refresh/ with refresh_token
5. Get new access_token, continue

Why JWT over sessions:
- Stateless: No session table in database
- Scalable: Works across multiple servers
- Mobile-friendly: Tokens can be stored on client
- Embeds tenant_id: Token includes tenant context
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import LoginSerializer, UserProfileSerializer, TokenRefreshResponseSerializer
from rest_framework_simplejwt.serializers import TokenRefreshSerializer


class LoginView(APIView):
    """
    POST /api/auth/login/

    Input:
    {
      "username": "alice",
      "password": "secure_password"
    }

    Output:
    {
      "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
      "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
      "user": {
        "id": "user-1",
        "username": "alice",
        "email": "alice@example.com",
        "tenant": {
          "id": "tenant-1",
          "name": "Acme Corp",
          "slug": "acme"
        },
        "role": "ANALYST"
      }
    }

    Why custom LoginView instead of TokenObtainPairView:
    - Standard simplejwt only returns tokens
    - We need to return user profile (tenant, role)
    - Custom validation includes tenant_id embedding
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RefreshTokenView(APIView):
    """
    POST /api/auth/refresh/

    Input:
    {
      "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
    }

    Output:
    {
      "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
    }

    Standard simplejwt refresh endpoint.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        response_data = {
            'access': serializer.validated_data['access']
        }

        return Response(response_data, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    """
    GET /api/auth/me/

    Returns the logged-in user's profile.
    Requires valid JWT token.

    Output:
    {
      "id": "user-1",
      "username": "alice",
      "email": "alice@example.com",
      "tenant": {...},
      "role": "ANALYST"
    }

    Use case: Frontend calls this on app load to get user context.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.profile
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    POST /api/auth/logout/

    Frontend can call this to invalidate refresh token (blacklist it).
    For stateless JWT, logout is optional:
    - Frontend just deletes tokens from localStorage
    - Tokens expire automatically (15 min access, 7 days refresh)

    If you need immediate invalidation, implement token blacklist.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # In production with token blacklist:
        # blacklist = BlacklistedToken.objects.create(token=request.auth)

        return Response(
            {'message': 'Logged out successfully'},
            status=status.HTTP_200_OK
        )
