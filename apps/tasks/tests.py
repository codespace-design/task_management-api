from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .models import Task


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
        self.assertEqual(response.data[0]["id"], self.task.id)

    def test_list_tasks(self):
        response = self.client.get("/api/tasks/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["title"], self.task.title)

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

    def test_retrieve_task(self):
        response = self.client.get(f"/api/tasks/{self.task.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.task.pk)

    def test_update_task(self):
        self.authenticate_as(User.Role.EMPLOYER)
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
        self.authenticate_as(User.Role.EMPLOYER)
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
        self.authenticate_as(User.Role.EMPLOYER)
        response = self.client.delete(f"/api/tasks/{self.task.pk}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Task.objects.count(), 0)

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
        self.assertEqual(Task.objects.count(), 1)

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
        self.assertIn("title", response.data)

    def authenticate_as(self, role):
        user = User.objects.create_user(
            email=f"{role}-user@example.com",
            password="A-strong-test-password-2026",
            role=role,
        )
        self.client.force_authenticate(user)


class TaskDashboardTestCase(APITestCase):
    def test_dashboard_is_available(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTemplateUsed(response, "tasks/dashboard.html")
        self.assertContains(response, "tasks/dashboard.css")
        self.assertContains(response, "tasks/dashboard.js")
        self.assertContains(response, 'id="auth-form"')
