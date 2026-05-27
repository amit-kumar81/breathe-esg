"""
API integration tests for breathe/apps/auth/views.py

Covers:
  POST /api/auth/login/   — valid credentials, wrong password, missing fields
  POST /api/auth/refresh/ — token refresh
  GET  /api/auth/me/      — current user profile
  POST /api/auth/logout/  — logout

Also tests UserProfile.has_permission for role-based access logic.
"""

from breathe.tests.base import BaseBreatheTestCase
from breathe.apps.auth.models import UserProfile
from rest_framework_simplejwt.tokens import RefreshToken


class LoginViewTests(BaseBreatheTestCase):

    def test_valid_login_returns_200(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "admin_user", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_valid_login_returns_access_token(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "admin_user", "password": "testpass123"},
            format="json",
        )
        self.assertIn("access", resp.data)
        self.assertTrue(len(resp.data["access"]) > 10)

    def test_valid_login_returns_refresh_token(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "admin_user", "password": "testpass123"},
            format="json",
        )
        self.assertIn("refresh", resp.data)

    def test_valid_login_returns_user_object(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "admin_user", "password": "testpass123"},
            format="json",
        )
        self.assertIn("user", resp.data)
        self.assertEqual(resp.data["user"]["username"], "admin_user")

    def test_valid_login_returns_correct_role(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "analyst_user", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.data["user"]["role"], "ANALYST")

    def test_valid_login_returns_tenant_info(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "admin_user", "password": "testpass123"},
            format="json",
        )
        tenant = resp.data["user"]["tenant"]
        self.assertIn("id", tenant)
        self.assertIn("name", tenant)
        self.assertIn("slug", tenant)

    def test_wrong_password_returns_400(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "admin_user", "password": "wrong_password"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_wrong_username_returns_400(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "nonexistent_user", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_missing_username_returns_400(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_missing_password_returns_400(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "admin_user"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_empty_body_returns_400(self):
        resp = self.client.post("/api/auth/login/", {}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_disabled_user_returns_400(self):
        profile = UserProfile.objects.get(user=self.analyst)
        profile.is_active = False
        profile.save()
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "analyst_user", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_user_without_profile_returns_400(self):
        from django.contrib.auth.models import User
        orphan = User.objects.create_user(username="orphan", password="pass123")
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "orphan", "password": "pass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_all_four_roles_can_login(self):
        users = [
            ("admin_user", "ADMIN"),
            ("analyst_user", "ANALYST"),
            ("provider_user", "DATA_PROVIDER"),
            ("viewer_user", "VIEWER"),
        ]
        for username, role in users:
            resp = self.client.post(
                "/api/auth/login/",
                {"username": username, "password": "testpass123"},
                format="json",
            )
            self.assertEqual(resp.status_code, 200, f"Login failed for {username}")
            self.assertEqual(resp.data["user"]["role"], role)


class RefreshTokenViewTests(BaseBreatheTestCase):

    def test_valid_refresh_returns_200(self):
        refresh = RefreshToken.for_user(self.admin)
        resp = self.client.post(
            "/api/auth/refresh/",
            {"refresh": str(refresh)},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_valid_refresh_returns_new_access_token(self):
        refresh = RefreshToken.for_user(self.admin)
        resp = self.client.post(
            "/api/auth/refresh/",
            {"refresh": str(refresh)},
            format="json",
        )
        self.assertIn("access", resp.data)

    def test_expired_refresh_token_returns_non_200(self):
        from datetime import timedelta
        from rest_framework_simplejwt.tokens import RefreshToken
        from django.utils import timezone
        refresh = RefreshToken.for_user(self.admin)
        refresh.set_exp(from_time=timezone.now() - timedelta(days=100))
        token_str = str(refresh)
        # simplejwt raises TokenError for expired tokens; may propagate as 500
        # if DRF exception handler doesn't intercept it. Use raise_request_exception=False.
        self.client.raise_request_exception = False
        resp = self.client.post(
            "/api/auth/refresh/",
            {"refresh": token_str},
            format="json",
        )
        # Must NOT succeed — expired token must not return a new access token
        self.assertNotEqual(resp.status_code, 200)

    def test_missing_refresh_token_returns_400(self):
        resp = self.client.post("/api/auth/refresh/", {}, format="json")
        self.assertEqual(resp.status_code, 400)


class CurrentUserViewTests(BaseBreatheTestCase):

    def test_me_authenticated_returns_200(self):
        self.auth(self.admin)
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, 200)

    def test_me_unauthenticated_returns_401(self):
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, 401)

    def test_me_returns_correct_username(self):
        self.auth(self.analyst)
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.data["username"], "analyst_user")

    def test_me_returns_role(self):
        self.auth(self.analyst)
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.data["role"], "ANALYST")

    def test_me_returns_tenant_info(self):
        self.auth(self.admin)
        resp = self.client.get("/api/auth/me/")
        self.assertIn("tenant", resp.data)
        self.assertEqual(resp.data["tenant"]["slug"], "test-corp")

    def test_me_returns_is_active(self):
        self.auth(self.admin)
        resp = self.client.get("/api/auth/me/")
        self.assertIn("is_active", resp.data)
        self.assertTrue(resp.data["is_active"])

    def test_me_each_role_returns_correct_role(self):
        role_map = [
            (self.admin, "ADMIN"),
            (self.analyst, "ANALYST"),
            (self.provider, "DATA_PROVIDER"),
            (self.viewer, "VIEWER"),
        ]
        for user, expected_role in role_map:
            self.auth(user)
            resp = self.client.get("/api/auth/me/")
            self.assertEqual(resp.data["role"], expected_role)


class LogoutViewTests(BaseBreatheTestCase):

    def test_logout_authenticated_returns_200(self):
        self.auth(self.admin)
        resp = self.client.post("/api/auth/logout/")
        self.assertEqual(resp.status_code, 200)

    def test_logout_unauthenticated_returns_401(self):
        resp = self.client.post("/api/auth/logout/")
        self.assertEqual(resp.status_code, 401)

    def test_logout_response_message(self):
        self.auth(self.admin)
        resp = self.client.post("/api/auth/logout/")
        self.assertIn("message", resp.data)


class UserProfilePermissionsTests(BaseBreatheTestCase):
    """Unit tests for UserProfile.has_permission role logic."""

    def _profile(self, user):
        return UserProfile.objects.get(user=user)

    def test_admin_has_all_permissions(self):
        p = self._profile(self.admin)
        self.assertTrue(p.has_permission("approve_records"))
        self.assertTrue(p.has_permission("upload_data"))
        self.assertTrue(p.has_permission("view_data"))
        self.assertTrue(p.has_permission("some_other_permission"))

    def test_analyst_can_approve_records(self):
        p = self._profile(self.analyst)
        self.assertTrue(p.has_permission("approve_records"))

    def test_analyst_cannot_upload_data(self):
        p = self._profile(self.analyst)
        self.assertFalse(p.has_permission("upload_data"))

    def test_analyst_can_view_data(self):
        p = self._profile(self.analyst)
        self.assertTrue(p.has_permission("view_data"))

    def test_data_provider_can_upload_data(self):
        p = self._profile(self.provider)
        self.assertTrue(p.has_permission("upload_data"))

    def test_data_provider_cannot_approve_records(self):
        p = self._profile(self.provider)
        self.assertFalse(p.has_permission("approve_records"))

    def test_data_provider_cannot_view_data(self):
        p = self._profile(self.provider)
        self.assertFalse(p.has_permission("view_data"))

    def test_viewer_can_view_data(self):
        p = self._profile(self.viewer)
        self.assertTrue(p.has_permission("view_data"))

    def test_viewer_cannot_approve_or_upload(self):
        p = self._profile(self.viewer)
        self.assertFalse(p.has_permission("approve_records"))
        self.assertFalse(p.has_permission("upload_data"))

    def test_viewer_cannot_do_admin_actions(self):
        p = self._profile(self.viewer)
        self.assertFalse(p.has_permission("delete_everything"))
