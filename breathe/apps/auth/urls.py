"""Auth URL routing."""

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
