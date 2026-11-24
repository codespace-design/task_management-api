from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .models import Job


class JobAPITests(APITestCase):
    password = "A-strong-test-password-2026"

    def setUp(self):
        self.employer = User.objects.create_user(
            email="job-employer@example.com",
            password=self.password,
            role=User.Role.EMPLOYER,
        )
        self.other_employer = User.objects.create_user(
            email="other-job-employer@example.com",
            password=self.password,
            role=User.Role.EMPLOYER,
        )
        self.candidate = User.objects.create_user(
            email="job-candidate@example.com",
            password=self.password,
            role=User.Role.CANDIDATE,
        )
        self.client.force_authenticate(self.employer)
        self.list_url = "/api/jobs/"
        self.payload = {
            "title": "Senior Python Engineer",
            "description": "Build and maintain reliable API services.",
            "skills": ["Python", "Django", "Python"],
            "experience": "5+ years building backend applications",
            "minimum_salary": "100000.00",
            "maximum_salary": "150000.00",
            "location": "Remote, US",
            "job_type": Job.JobType.FULL_TIME,
        }

    def test_employer_can_create_job_and_server_sets_owner_and_draft_status(self):
        response = self.client.post(self.list_url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["employer"], self.employer.pk)
        self.assertEqual(response.data["status"], Job.Status.DRAFT)
        self.assertEqual(response.data["skills"], ["Python", "Django"])
        self.assertEqual(Job.objects.get().employer, self.employer)

    def test_employer_cannot_spoof_owner_or_initial_status(self):
        response = self.client.post(
            self.list_url,
            {**self.payload, "employer": self.other_employer.pk, "status": "active"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job = Job.objects.get()
        self.assertEqual(job.employer, self.employer)
        self.assertEqual(job.status, Job.Status.DRAFT)

    def test_candidates_cannot_create_or_edit_jobs(self):
        job = Job.objects.create(employer=self.employer, **self.payload)
        self.client.force_authenticate(self.candidate)

        create = self.client.post(self.list_url, self.payload, format="json")
        update = self.client.patch(
            f"{self.list_url}{job.pk}/",
            {"title": "Candidate edit"},
            format="json",
        )

        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(update.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Job.objects.count(), 1)

    def test_employers_can_only_list_and_update_their_own_jobs(self):
        own_job = Job.objects.create(employer=self.employer, **self.payload)
        other_job = Job.objects.create(employer=self.other_employer, **self.payload)

        listed = self.client.get(self.list_url)
        own_update = self.client.patch(
            f"{self.list_url}{own_job.pk}/",
            {"title": "Updated role"},
            format="json",
        )
        other_update = self.client.patch(
            f"{self.list_url}{other_job.pk}/",
            {"title": "Unauthorized edit"},
            format="json",
        )

        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listed.data), 1)
        self.assertEqual(listed.data[0]["id"], own_job.pk)
        self.assertEqual(own_update.status_code, status.HTTP_200_OK)
        self.assertEqual(other_update.status_code, status.HTTP_404_NOT_FOUND)
        other_job.refresh_from_db()
        self.assertEqual(other_job.title, self.payload["title"])

    def test_candidate_can_only_read_active_jobs(self):
        draft = Job.objects.create(employer=self.employer, **self.payload)
        active = Job.objects.create(
            employer=self.other_employer,
            status=Job.Status.ACTIVE,
            **self.payload,
        )
        self.client.force_authenticate(self.candidate)

        listed = self.client.get(self.list_url)
        draft_detail = self.client.get(f"{self.list_url}{draft.pk}/")
        active_detail = self.client.get(f"{self.list_url}{active.pk}/")

        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listed.data), 1)
        self.assertEqual(listed.data[0]["id"], active.pk)
        self.assertEqual(draft_detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(active_detail.status_code, status.HTTP_200_OK)

    def test_employer_can_activate_and_deactivate_owned_job(self):
        job = Job.objects.create(employer=self.employer, **self.payload)
        url = f"{self.list_url}{job.pk}/"

        activated = self.client.post(f"{url}activate/")
        deactivated = self.client.post(f"{url}deactivate/")

        self.assertEqual(activated.status_code, status.HTTP_200_OK)
        self.assertEqual(activated.data["status"], Job.Status.ACTIVE)
        self.assertEqual(deactivated.status_code, status.HTTP_200_OK)
        self.assertEqual(deactivated.data["status"], Job.Status.INACTIVE)

    def test_employer_cannot_change_another_owners_job_status(self):
        job = Job.objects.create(employer=self.other_employer, **self.payload)

        response = self.client.post(f"{self.list_url}{job.pk}/activate/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.DRAFT)

    def test_salary_range_must_be_valid(self):
        response = self.client.post(
            self.list_url,
            {**self.payload, "minimum_salary": "150000", "maximum_salary": "100000"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("maximum_salary", response.data["errors"])
        self.assertEqual(Job.objects.count(), 0)

    def test_skills_must_be_a_list_of_non_empty_strings(self):
        response = self.client.post(
            self.list_url,
            {**self.payload, "skills": ["Python", ""]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("skills", response.data["errors"])

    def test_job_api_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
