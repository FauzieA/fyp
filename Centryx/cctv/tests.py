from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from djoser.utils import encode_uid
from rest_framework import status
from rest_framework.test import APIClient

# ====================================================================================================
# Tests for User Authentication Endpoints
# ====================================================================================================


class UserAuthTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Create a test user
        self.user_data = {
            "username": "testuser",
            "password": "Testpass123!",
            "email": "testuser@example.com"
        }
        self.user = User.objects.create_user(**self.user_data)

    def test_user_is_not_admin(self):
        # Test user role is not admin
        self.assertFalse(self.user.is_superuser)
        self.assertFalse(self.user.is_staff)

    def test_get_current_user_info(self):
        """Test retrieving current user info using JWT"""
        # First, login to get access token
        response = self.client.post("/auth/jwt/create/", {
            "username": self.user_data["username"],
            "password": self.user_data["password"]
        })
        access_token = response.data["access"]

        # Use token to get current user info
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get("/auth/users/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], self.user_data["username"])
        self.assertEqual(response.data["email"], self.user_data["email"])

    def test_jwt_login(self):
        # Test JWT token obtain endpoint
        response = self.client.post("/auth/jwt/create/", {
            "username": self.user_data["username"],
            "password": self.user_data["password"]
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_jwt_refresh(self):
        # Get a new access token using the refresh token
        response = self.client.post("/auth/jwt/create/", {
            "username": self.user_data["username"],
            "password": self.user_data["password"]
        })
        refresh_token = response.data["refresh"]

        # Test refresh endpoint
        response = self.client.post(
            "/auth/jwt/refresh/", {"refresh": refresh_token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_change_password(self):
        """Test changing the user's password using Djoser endpoint"""
        # First, login to get access token
        response = self.client.post("/auth/jwt/create/", {
            "username": self.user_data["username"],
            "password": self.user_data["password"]
        })
        access_token = response.data["access"]

        # Set authorization header
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Change password
        new_password_data = {
            "current_password": self.user_data["password"],
            "new_password": "Newpass456!"
        }
        response = self.client.post(
            "/auth/users/set_password/",
            new_password_data)

        # Assert that password change was successful
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # verify that login with new password works
        response = self.client.post("/auth/jwt/create/", {
            "username": self.user_data["username"],
            "password": "Newpass456!"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_update_user_info(self):
        response = self.client.post("/auth/jwt/create/", {
            "username": self.user_data["username"],
            "password": self.user_data["password"]
        })
        access_token = response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = self.client.patch("/auth/users/me/", {
            "email": "newemail@example.com"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only test email as Djoser returns this by default
        self.assertEqual(response.data["email"], "newemail@example.com")


class UserActivationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_data = {
            "username": "testuser",
            "email": "newtest11@gmail.com",
            "password": "Testpass123!",
            "re_password": "Testpass123!"
        }

    def test_user_activation_workflow(self):
        # 1) Create user
        response = self.client.post("/auth/users/", self.user_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username="testuser")
        self.assertFalse(user.is_active)

        # 2) Attempt login before activation
        response = self.client.post("/auth/jwt/create/", {
            "username": self.user_data["username"],
            "password": self.user_data["password"]
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # 3) Activate user
        uid = encode_uid(user.pk)
        token = default_token_generator.make_token(user)  # <-- correct way
        response = self.client.post("/auth/users/activation/", {
            "uid": uid,
            "token": token
        })
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        user.refresh_from_db()
        self.assertTrue(user.is_active)

        # 4) Login after activation
        response = self.client.post("/auth/jwt/create/", {
            "username": self.user_data["username"],
            "password": self.user_data["password"]
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)


class UserPasswordResetTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_data = {
            "username": "testuser",
            "email": "test11@gmail.com",
            "password": "Testpass123!"
        }
        self.user = User.objects.create_user(**self.user_data)
        self.user.is_active = True
        self.user.save()

    def test_password_reset_workflow(self):
        # 1) Request password reset
        response = self.client.post("/auth/users/reset_password/", {
            "email": self.user_data["email"]
        })
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # 2) Generate token & uid for testing
        uid = encode_uid(self.user.pk)
        token = default_token_generator.make_token(self.user)

        # 3) Confirm password reset
        new_password = "Newpass456!"
        response = self.client.post("/auth/users/reset_password_confirm/", {
            "uid": uid,
            "token": token,
            "new_password": new_password
        })
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # 4) Login with the new password
        response = self.client.post("/auth/jwt/create/", {
            "username": self.user_data["username"],
            "password": new_password
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)


# Override email backend to use in-memory backend for testing
@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
)
class UserEmailTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_data = {
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "Testpass123!",
            "re_password": "Testpass123!"
        }

    def test_user_activation_email_sent(self):
        # Create user (Djoser should send activation email)
        response = self.client.post("/auth/users/", self.user_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check that an email was sent
        self.assertEqual(len(mail.outbox), 1)
        activation_email = mail.outbox[0]

        # Flexible subject check
        self.assertIn("Account activation", activation_email.subject)
        self.assertIn(self.user_data["email"], activation_email.to)

    def test_password_reset_email_sent(self):
        # Create user
        user = User.objects.create_user(
            username=self.user_data["username"],
            email=self.user_data["email"],
            password=self.user_data["password"],
        )
        user.is_active = True
        user.save()

        # Request password reset
        response = self.client.post("/auth/users/reset_password/", {
            "email": self.user_data["email"]
        })
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Check that an email was sent
        self.assertEqual(len(mail.outbox), 1)
        reset_email = mail.outbox[0]

        # Flexible subject check
        self.assertIn("Password reset", reset_email.subject)
        self.assertIn(self.user_data["email"], reset_email.to)


# ====================================================================================================
# End of Tests for User Authentication Endpoints
# ====================================================================================================


# ====================================================================================================
# Tests fçr CCTV Application
# ====================================================================================================


# ====================================================================================================
# End of Tests for CCTV Application
# ====================================================================================================
