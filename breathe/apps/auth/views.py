"""Auth views: login, token refresh, current user, logout."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import LoginSerializer, UserProfileSerializer, TokenRefreshResponseSerializer
from rest_framework_simplejwt.serializers import TokenRefreshSerializer


class LoginView(APIView):
    """POST /api/auth/login/ — returns JWT tokens + user profile."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RefreshTokenView(APIView):
    """POST /api/auth/refresh/ — returns a new access token."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        response_data = {
            'access': serializer.validated_data['access']
        }

        return Response(response_data, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    """GET /api/auth/me/ — returns the logged-in user's profile."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.profile
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """POST /api/auth/logout/ — frontend deletes tokens; this endpoint is a no-op for stateless JWT."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(
            {'message': 'Logged out successfully'},
            status=status.HTTP_200_OK
        )
