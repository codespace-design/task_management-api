from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .models import Job, JobSkill


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
            "minimum_experience_years": 3,
            "maximum_experience_years": 6,
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
        self.assertEqual(response.data["skills"], ["Django", "Python"])
        self.assertEqual(Job.objects.get().employer, self.employer)

    def test_employer_cannot_spoof_owner_or_initial_status(self):
        response = self.client.post(
            self.list_url,
            {
                **self.payload,
                "employer": self.other_employer.pk,
                "status": "active",
                "is_featured": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job = Job.objects.get()
        self.assertEqual(job.employer, self.employer)
        self.assertEqual(job.status, Job.Status.DRAFT)
        self.assertFalse(job.is_featured)

    def test_candidates_cannot_create_or_edit_jobs(self):
        job = self.create_job()
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
        own_job = self.create_job()
        other_job = self.create_job(employer=self.other_employer)

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
        self.assertEqual(listed.data["count"], 1)
        self.assertEqual(listed.data["results"][0]["id"], own_job.pk)
        self.assertEqual(own_update.status_code, status.HTTP_200_OK)
        self.assertEqual(other_update.status_code, status.HTTP_404_NOT_FOUND)
        other_job.refresh_from_db()
        self.assertEqual(other_job.title, self.payload["title"])

    def test_candidate_can_only_read_active_jobs(self):
        draft = self.create_job()
        active = self.create_job(
            employer=self.other_employer,
            status=Job.Status.ACTIVE,
        )
        self.client.force_authenticate(self.candidate)

        listed = self.client.get(self.list_url)
        draft_detail = self.client.get(f"{self.list_url}{draft.pk}/")
        active_detail = self.client.get(f"{self.list_url}{active.pk}/")

        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["count"], 1)
        self.assertEqual(listed.data["results"][0]["id"], active.pk)
        self.assertEqual(draft_detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(active_detail.status_code, status.HTTP_200_OK)

    def test_employer_can_activate_and_deactivate_owned_job(self):
        job = self.create_job()
        url = f"{self.list_url}{job.pk}/"

        activated = self.client.post(f"{url}activate/")
        deactivated = self.client.post(f"{url}deactivate/")

        self.assertEqual(activated.status_code, status.HTTP_200_OK)
        self.assertEqual(activated.data["status"], Job.Status.ACTIVE)
        self.assertEqual(deactivated.status_code, status.HTTP_200_OK)
        self.assertEqual(deactivated.data["status"], Job.Status.INACTIVE)

    def test_employer_cannot_change_another_owners_job_status(self):
        job = self.create_job(employer=self.other_employer)

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

    def test_public_job_listing_does_not_require_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_featured_and_latest_list_only_active_jobs(self):
        featured = self.create_job(
            status=Job.Status.ACTIVE,
            is_featured=True,
        )
        latest = self.create_job(
            employer=self.other_employer,
            status=Job.Status.ACTIVE,
        )
        self.create_job(
            status=Job.Status.DRAFT,
            is_featured=True,
        )
        self.client.force_authenticate(user=None)

        featured_response = self.client.get(f"{self.list_url}featured/")
        latest_response = self.client.get(f"{self.list_url}latest/")

        self.assertEqual(featured_response.status_code, status.HTTP_200_OK)
        self.assertEqual(featured_response.data["count"], 1)
        self.assertEqual(featured_response.data["results"][0]["id"], featured.pk)
        self.assertEqual(latest_response.data["count"], 2)
        self.assertEqual(latest_response.data["results"][0]["id"], latest.pk)

    def test_job_search_and_filters_can_be_combined(self):
        matching = self.create_job(
            status=Job.Status.ACTIVE,
        )
        self.create_job(
            employer=self.other_employer,
            status=Job.Status.ACTIVE,
            title="Java Developer",
            description="Build enterprise services.",
            skills=["Java"],
            experience="8+ years",
            minimum_experience_years=8,
            maximum_experience_years=10,
            minimum_salary="160000.00",
            maximum_salary="180000.00",
            location="New York, US",
            job_type=Job.JobType.CONTRACT,
        )
        self.client.force_authenticate(user=None)

        response = self.client.get(
            self.list_url,
            {
                "search": "Python Engineer",
                "skill": "python",
                "location": "remote",
                "job_type": Job.JobType.FULL_TIME,
                "min_experience_years": 4,
                "max_experience_years": 5,
                "min_salary": "120000",
                "max_salary": "140000",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], matching.pk)

    def test_job_list_paginates_and_caps_requested_page_size(self):
        Job.objects.bulk_create(
            [
                Job(
                    employer=self.employer,
                    title=f"Job {index}",
                    description="Job description",
                    experience="Experience varies",
                    location="Remote",
                    job_type=Job.JobType.FULL_TIME,
                    status=Job.Status.ACTIVE,
                )
                for index in range(25)
            ]
        )
        self.client.force_authenticate(user=None)

        response = self.client.get(f"{self.list_url}?page_size=3&page=2")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 3)
        self.assertIsNotNone(response.data["next"])
        self.assertIsNotNone(response.data["previous"])

    def test_invalid_filter_values_return_validation_errors(self):
        self.client.force_authenticate(user=None)
        invalid_queries = (
            "?job_type=invalid",
            "?min_salary=not-a-number",
            "?min_experience_years=-1",
            "?min_salary=200000&max_salary=100000",
            "?min_experience_years=8&max_experience_years=4",
        )

        for query in invalid_queries:
            with self.subTest(query=query):
                response = self.client.get(f"{self.list_url}{query}")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def create_job(
        self,
        employer=None,
        status=Job.Status.DRAFT,
        is_featured=False,
        **overrides,
    ):
        values = {**self.payload, **overrides}
        skill_names = values.pop("skills", [])
        job = Job.objects.create(
            employer=employer or self.employer,
            status=status,
            is_featured=is_featured,
            **values,
        )
        JobSkill.objects.bulk_create(
            [
                JobSkill(job=job, name=name, normalized_name=name.casefold())
                for name in dict.fromkeys(skill_names)
            ]
        )
        return job
