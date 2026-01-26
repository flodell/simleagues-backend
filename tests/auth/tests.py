from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class AuthMixin:
    def create_and_login(
        self, username="test", email="test@example.com", password="TestPass123!"
    ):
        self.user = User.objects.create_user(
            username=username, email=email, password=password
        )
        res = self.client.post(
            reverse("login"), {"username": username, "password": password}
        )
        self.access_token = res.data["access"]
        self.refresh_token = res.data["refresh"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        return res


class RegisterTestCase(APITestCase):

    def setUp(self):
        self.url = reverse("register")

    def test_register_success(self):
        data = {
            "username": "test",
            "email": "test@example.com",
            "password": "SecurePass123!",
            "confirmed_password": "SecurePass123!",
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username=data["username"]).exists())

    def test_register_password_mismatch(self):
        data = {
            "username": "test",
            "email": "test@example.com",
            "password": "SecurePass123!",
            "confirmed_password": "SecurePass183!",
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_username(self):
        User.objects.create_user("existing", "exist@example.com", "pass123")
        data = {
            "username": "existing",
            "email": "new@example.com",
            "password": "SecurePass123!",
            "confirmed_password": "SecurePass123!",
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_weak_password(self):
        data = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "123",
            "confirmed_password": "123",
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTests(APITestCase):

    def setUp(self):
        self.url = reverse("login")
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="TestPass123!"
        )

    def test_login_success(self):
        response = self.client.post(
            self.url, {"username": "test", "password": "TestPass123!"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_wrong_password(self):
        response = self.client.post(
            self.url, {"username": "test", "password": "WrongPass!"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_user(self):
        response = self.client.post(
            self.url, {"username": "noone", "password": "TestPass123!"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RefreshTests(AuthMixin, APITestCase):

    def setUp(self):
        self.url = reverse("refresh_token")
        self.create_and_login()

    def test_refresh_success(self):
        response = self.client.post(
            self.url, {"refresh": self.refresh_token}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_refresh_invalid_token(self):
        response = self.client.post(
            self.url, {"refresh": "invalid_token"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutTests(AuthMixin, APITestCase):

    def setUp(self):
        self.url = reverse("logout")
        self.create_and_login()

    def test_logout_success(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        response = self.client.post(
            self.url, {"refresh": self.refresh_token}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_logout_blacklists_token(self):
        """After logout, refresh token should be unusable"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        logout_res = self.client.post(
            self.url, {"refresh": self.refresh_token}, format="json"
        )

        self.assertEqual(logout_res.status_code, status.HTTP_204_NO_CONTENT)
        # Try to use blacklisted refresh token
        response = self.client.post(
            reverse("refresh_token"), {"refresh": self.refresh_token}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_auth(self):
        self.client.credentials()  # Clear auth
        response = self.client.post(
            self.url, {"refresh": self.refresh_token}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MeTests(AuthMixin, APITestCase):

    def setUp(self):
        self.url = reverse("me")
        self.create_and_login()

    def test_me_success(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "test")
        self.assertEqual(response.data["email"], "test@example.com")

    def test_me_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_username(self):
        response = self.client.patch(self.url, {"username": "newname"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "newname")

    def test_update_email(self):
        response = self.client.patch(
            self.url, {"email": "new@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "new@example.com")


class UpdatePasswordTests(AuthMixin, APITestCase):

    def setUp(self):
        self.url = reverse("update_password")
        self.create_and_login()

    def test_update_password_success(self):
        response = self.client.post(
            self.url,
            {"current_password": "TestPass123!", "new_password": "NewSecure456!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecure456!"))

    def test_update_password_wrong_current(self):
        response = self.client.post(
            self.url,
            {"current_password": "WrongPass!", "new_password": "NewSecure456!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_password_weak_new(self):
        response = self.client.post(
            self.url,
            {"current_password": "TestPass123!", "new_password": "123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_password_unauthenticated(self):
        self.client.credentials()
        response = self.client.post(
            self.url,
            {"current_password": "TestPass123!", "new_password": "NewSecure456!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
