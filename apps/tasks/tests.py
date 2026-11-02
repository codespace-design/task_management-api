from rest_framework import status
from rest_framework.test import APITestCase

from .models import Task


class TaskAPITestCase(APITestCase):
    def setUp(self):
        self.task = Task.objects.create(
            title="Write project brief",
            description="Prepare the project overview for the sprint review.",
            completed=False,
        )

    def test_list_tasks(self):
        response = self.client.get("/api/tasks/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["title"], self.task.title)

    def test_create_task(self):
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
        response = self.client.delete(f"/api/tasks/{self.task.pk}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Task.objects.count(), 0)

    def test_blank_title_rejected(self):
        response = self.client.post(
            "/api/tasks/",
            {"title": "   ", "description": "x"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)
