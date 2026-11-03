from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from .models import CandidateProfile, EmployerProfile

User = get_user_model()


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
