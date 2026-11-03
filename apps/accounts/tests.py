from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .models import CandidateProfile, EmployerProfile, User


class UserManagerTests(TestCase):
    def test_create_user_normalizes_email_and_hashes_password(self):
        user = User.objects.create_user(
            email="  Person@Example.com ",
            password="A-strong-test-password-2026",
            role=User.Role.CANDIDATE,
        )

        self.assertEqual(user.email, "person@example.com")
        self.assertTrue(user.check_password("A-strong-test-password-2026"))
        self.assertFalse(user.is_verified)
        self.assertTrue(hasattr(user, "candidate_profile"))

    def test_create_user_requires_a_role(self):
        with self.assertRaisesMessage(ValueError, "A valid role is required."):
            User.objects.create_user(
                email="person@example.com",
                password="A-strong-test-password-2026",
            )

    def test_create_user_allows_multiple_accounts_without_phone_numbers(self):
        first = User.objects.create_user(
            email="first@example.com",
            password="A-strong-test-password-2026",
            role=User.Role.CANDIDATE,
        )
        second = User.objects.create_user(
            email="second@example.com",
            password="A-strong-test-password-2026",
            role=User.Role.EMPLOYER,
        )

        self.assertIsNone(first.phone)
        self.assertIsNone(second.phone)

    def test_superuser_gets_admin_role(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="A-strong-test-password-2026",
        )

        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


class RegistrationAPITests(APITestCase):
    url = "/api/auth/register/"
    password = "A-strong-test-password-2026"

    def test_candidate_registration_creates_candidate_profile(self):
        response = self.client.post(
            self.url,
            {
                "email": "candidate@example.com",
                "phone": "+1 555 0100",
                "role": User.Role.CANDIDATE,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="candidate@example.com")
        self.assertEqual(user.role, User.Role.CANDIDATE)
        self.assertTrue(user.check_password(self.password))
        self.assertFalse(user.is_verified)
        self.assertTrue(CandidateProfile.objects.filter(user=user).exists())
        self.assertFalse(EmployerProfile.objects.filter(user=user).exists())
        self.assertNotIn("password", response.data)

    def test_employer_registration_creates_employer_profile(self):
        response = self.client.post(
            self.url,
            {
                "email": "employer@example.com",
                "role": User.Role.EMPLOYER,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="employer@example.com")
        self.assertTrue(EmployerProfile.objects.filter(user=user).exists())

    def test_admin_role_cannot_be_selected_at_registration(self):
        response = self.client.post(
            self.url,
            {
                "email": "admin@example.com",
                "role": User.Role.ADMIN,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="admin@example.com").exists())

    def test_role_is_required_at_registration(self):
        response = self.client.post(
            self.url,
            {"email": "candidate@example.com", "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)

    def test_registration_rejects_case_insensitive_duplicate_email(self):
        User.objects.create_user(
            email="candidate@example.com",
            password=self.password,
            role=User.Role.CANDIDATE,
        )

        response = self.client.post(
            self.url,
            {
                "email": "CANDIDATE@EXAMPLE.COM",
                "role": User.Role.CANDIDATE,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_registration_rejects_duplicate_phone(self):
        User.objects.create_user(
            email="existing@example.com",
            password=self.password,
            role=User.Role.CANDIDATE,
            phone="+15550100",
        )

        response = self.client.post(
            self.url,
            {
                "email": "new@example.com",
                "phone": "+15550100",
                "role": User.Role.CANDIDATE,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", response.data)

    def test_weak_password_is_rejected(self):
        response = self.client.post(
            self.url,
            {
                "email": "candidate@example.com",
                "role": User.Role.CANDIDATE,
                "password": "password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)


class JWTAuthenticationTests(APITestCase):
    token_url = "/api/auth/token/"
    refresh_url = "/api/auth/token/refresh/"
    logout_url = "/api/auth/logout/"
    password = "A-strong-test-password-2026"

    def setUp(self):
        self.user = User.objects.create_user(
            email="jwt-user@example.com",
            password=self.password,
            role=User.Role.EMPLOYER,
        )

    def obtain_tokens(self, email=None):
        response = self.client.post(
            self.token_url,
            {"email": email or self.user.email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def test_login_returns_access_and_refresh_with_user_claims(self):
        tokens = self.obtain_tokens()

        self.assertIn("access", tokens)
        self.assertIn("refresh", tokens)
        access = AccessToken(tokens["access"])
        self.assertEqual(access["email"], self.user.email)
        self.assertEqual(access["role"], User.Role.EMPLOYER)

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(
            self.token_url,
            {"email": self.user.email, "password": "incorrect-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_rotates_and_blacklists_previous_refresh_token(self):
        tokens = self.obtain_tokens()

        response = self.client.post(
            self.refresh_url,
            {"refresh": tokens["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotEqual(response.data["refresh"], tokens["refresh"])
        replay = self.client.post(
            self.refresh_url,
            {"refresh": tokens["refresh"]},
            format="json",
        )
        self.assertEqual(replay.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_the_users_refresh_token(self):
        tokens = self.obtain_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = self.client.post(
            self.logout_url,
            {"refresh": tokens["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)
        replay = self.client.post(
            self.refresh_url,
            {"refresh": tokens["refresh"]},
            format="json",
        )
        self.assertEqual(replay.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_rejects_another_users_refresh_token(self):
        tokens = self.obtain_tokens()
        other_user = User.objects.create_user(
            email="other@example.com",
            password=self.password,
            role=User.Role.CANDIDATE,
        )
        other_tokens = self.obtain_tokens(email=other_user.email)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = self.client.post(
            self.logout_url,
            {"refresh": other_tokens["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.client.credentials()
        still_valid = self.client.post(
            self.refresh_url,
            {"refresh": other_tokens["refresh"]},
            format="json",
        )
        self.assertEqual(still_valid.status_code, status.HTTP_200_OK)
