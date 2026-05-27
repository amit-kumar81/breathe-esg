"""
Chunk 2.3: Multi-Tenancy Isolation - Auth URLs

Auth endpoints:
- POST /api/auth/login/ - Login with username + password
- POST /api/auth/refresh/ - Refresh access token
- GET /api/auth/me/ - Get current user profile
- POST /api/auth/logout/ - Logout (optional, invalidate token)
"""

from django.urls import path
from .views import (
    LoginView,
    RefreshTokenView,
    CurrentUserView,
    LogoutView
)

app_name = 'auth'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', RefreshTokenView.as_view(), name='refresh'),
    path('me/', CurrentUserView.as_view(), name='current_user'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
