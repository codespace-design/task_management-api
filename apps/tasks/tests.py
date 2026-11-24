import json
from datetime import timedelta

from django.conf import settings
from django.http import HttpResponseServerError
from django.test import RequestFactory
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from config.middleware import ApiServerErrorMiddleware

from .models import Task


class ApiServerErrorMiddlewareTests(APITestCase):
    def test_api_500_response_uses_the_standard_error_envelope(self):
        middleware = ApiServerErrorMiddleware(
            lambda request: HttpResponseServerError()
        )
        response = middleware(RequestFactory().get("/api/tasks/"))

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(
            json.loads(response.content),
            {
                "success": False,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "An unexpected server error occurred.",
                "errors": None,
            },
        )

    def test_non_api_500_response_is_unchanged(self):
        middleware = ApiServerErrorMiddleware(
            lambda request: HttpResponseServerError("failure")
        )
        response = middleware(RequestFactory().get("/"))

        self.assertEqual(response.content, b"failure")


class TaskAPITestCase(APITestCase):
    def setUp(self):
        self.task = Task.objects.create(
            title="Write project brief",
            description="Prepare the project overview for the sprint review.",
            completed=False,
        )
        self.user = User.objects.create_user(
            email="task-user@example.com",
            password="A-strong-test-password-2026",
            role=User.Role.CANDIDATE,
        )
        self.client.force_authenticate(self.user)

    def test_task_list_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/tasks/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["success"], False)
        self.assertEqual(
            response.data["status_code"],
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertIn("message", response.data)

    def test_jwt_token_can_access_task_list(self):
        self.client.force_authenticate(user=None)
        login = self.client.post(
            "/api/auth/token/",
            {
                "email": self.user.email,
                "password": "A-strong-test-password-2026",
            },
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        response = self.client.get("/api/tasks/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["id"], self.task.id)

    def test_list_tasks(self):
        response = self.client.get("/api/tasks/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["title"], self.task.title)
        self.assertEqual(response.data["count"], 1)

    def test_list_tasks_is_paginated_and_page_size_is_capped(self):
        Task.objects.bulk_create(
            [Task(title=f"Task {index}") for index in range(101)]
        )

        default_response = self.client.get("/api/tasks/")
        self.assertEqual(
            len(default_response.data["results"]),
            min(settings.API_PAGE_SIZE, 102),
        )
        self.assertEqual(
            default_response.data["next"] is not None,
            settings.API_PAGE_SIZE < 102,
        )

        response = self.client.get("/api/tasks/?page_size=1000")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 102)
        self.assertEqual(
            len(response.data["results"]),
            min(settings.API_MAX_PAGE_SIZE, 102),
        )
        self.assertEqual(
            response.data["next"] is not None,
            settings.API_MAX_PAGE_SIZE < 102,
        )

    def test_task_list_query_count_does_not_grow_with_page_size(self):
        Task.objects.bulk_create(
            [Task(title=f"Task {index}") for index in range(5)]
        )

        with self.assertNumQueries(2):
            response = self.client.get("/api/tasks/?page_size=6")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 6)

    def test_task_list_filters_by_creator_role_status_date_and_search(self):
        self.task.created_by = self.user
        self.task.save(update_fields=["created_by"])
        employer = User.objects.create_user(
            email="task-employer@example.com",
            password="A-strong-test-password-2026",
            role=User.Role.EMPLOYER,
        )
        Task.objects.create(
            title="Prepare interview",
            description="Searchable task description",
            completed=True,
            created_by=employer,
        )

        response = self.client.get(
            "/api/tasks/?role=employer&status=completed&search=searchable"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Prepare interview")
        self.assertEqual(response.data["results"][0]["created_by_role"], "employer")

    def test_task_list_filters_by_inclusive_created_date(self):
        today = timezone.localdate()
        yesterday = timezone.now() - timedelta(days=1)
        Task.objects.filter(pk=self.task.pk).update(created_at=yesterday)

        response = self.client.get(
            f"/api/tasks/?created_after={today.isoformat()}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

        response = self.client.get(
            f"/api/tasks/?created_before={today.isoformat()}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_task_list_rejects_invalid_filter_values(self):
        for query in (
            "?role=unknown",
            "?status=active",
            "?created_after=not-a-date",
            "?created_after=2026-03-02&created_before=2026-03-01",
        ):
            with self.subTest(query=query):
                response = self.client.get(f"/api/tasks/{query}")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_task(self):
        self.authenticate_as(User.Role.EMPLOYER)
        payload = {
            "title": "Review pull requests",
            "description": "Check pending review items.",
        }

        response = self.client.post("/api/tasks/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Task.objects.count(), 2)
        self.assertEqual(response.data["title"], payload["title"])
        self.assertEqual(response.data["created_by_role"], "employer")

    def test_retrieve_task(self):
        response = self.client.get(f"/api/tasks/{self.task.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.task.pk)

    def test_update_task(self):
        employer = self.authenticate_as(User.Role.EMPLOYER)
        self.task.created_by = employer
        self.task.save(update_fields=["created_by"])
        payload = {
            "title": "Updated task title",
            "description": "Updated description",
            "completed": True,
        }

        response = self.client.put(
            f"/api/tasks/{self.task.pk}/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, payload["title"])
        self.assertTrue(self.task.completed)

    def test_partial_update_task(self):
        employer = self.authenticate_as(User.Role.EMPLOYER)
        self.task.created_by = employer
        self.task.save(update_fields=["created_by"])
        payload = {"completed": True}

        response = self.client.patch(
            f"/api/tasks/{self.task.pk}/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.task.refresh_from_db()
        self.assertTrue(self.task.completed)

    def test_delete_task(self):
        employer = self.authenticate_as(User.Role.EMPLOYER)
        self.task.created_by = employer
        self.task.save(update_fields=["created_by"])
        response = self.client.delete(f"/api/tasks/{self.task.pk}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Task.objects.count(), 0)

    def test_employer_cannot_modify_another_employers_task(self):
        owner = User.objects.create_user(
            email="task-owner@example.com",
            password="A-strong-test-password-2026",
            role=User.Role.EMPLOYER,
        )
        self.task.created_by = owner
        self.task.save(update_fields=["created_by"])
        self.authenticate_as(User.Role.EMPLOYER)
        url = f"/api/tasks/{self.task.pk}/"

        update = self.client.patch(url, {"completed": True}, format="json")
        delete = self.client.delete(url)

        self.assertEqual(update.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete.status_code, status.HTTP_404_NOT_FOUND)
        self.task.refresh_from_db()
        self.assertFalse(self.task.completed)
        self.assertEqual(Task.objects.count(), 1)

    def test_admin_can_modify_another_users_task(self):
        self.authenticate_as(User.Role.ADMIN)

        response = self.client.patch(
            f"/api/tasks/{self.task.pk}/",
            {"completed": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.task.refresh_from_db()
        self.assertTrue(self.task.completed)

    def test_candidate_cannot_create_or_modify_tasks(self):
        self.authenticate_as(User.Role.CANDIDATE)
        url = f"/api/tasks/{self.task.pk}/"

        responses = (
            self.client.post(
                "/api/tasks/",
                {"title": "Candidate task"},
                format="json",
            ),
            self.client.put(
                url,
                {"title": "Changed task", "description": "", "completed": True},
                format="json",
            ),
            self.client.patch(url, {"completed": True}, format="json"),
            self.client.delete(url),
        )

        for response in responses:
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            self.assertEqual(response.data["status_code"], status.HTTP_403_FORBIDDEN)
        self.assertEqual(Task.objects.count(), 1)

    def test_missing_task_uses_standard_not_found_error(self):
        response = self.client.get("/api/tasks/999999999/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["status_code"], status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["errors"], None)

    def test_admin_can_create_tasks(self):
        self.authenticate_as(User.Role.ADMIN)
        response = self.client.post(
            "/api/tasks/",
            {"title": "Admin task"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Task.objects.count(), 2)

    def test_blank_title_rejected(self):
        self.authenticate_as(User.Role.EMPLOYER)
        response = self.client.post(
            "/api/tasks/",
            {"title": "   ", "description": "x"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["success"], False)
        self.assertEqual(response.data["status_code"], status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data["errors"])

    def authenticate_as(self, role):
        user = User.objects.create_user(
            email=f"{role}-user@example.com",
            password="A-strong-test-password-2026",
            role=role,
        )
        self.client.force_authenticate(user)
        return user


class TaskDashboardTestCase(APITestCase):
    def test_dashboard_is_available(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTemplateUsed(response, "tasks/dashboard.html")
        self.assertContains(response, "tasks/dashboard.css")
        self.assertContains(response, "tasks/dashboard.js")
        self.assertContains(response, 'id="auth-form"')
