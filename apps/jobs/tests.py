import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .models import Job, JobApplication, JobApplicationStatusHistory, JobSkill


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

    def test_employer_can_close_only_owned_jobs(self):
        own_job = self.create_job(status=Job.Status.ACTIVE)
        other_job = self.create_job(
            employer=self.other_employer,
            status=Job.Status.ACTIVE,
        )

        closed = self.client.post(f"{self.list_url}{own_job.pk}/close/")
        other_close = self.client.post(f"{self.list_url}{other_job.pk}/close/")

        self.assertEqual(closed.status_code, status.HTTP_200_OK)
        self.assertEqual(closed.data["status"], Job.Status.INACTIVE)
        self.assertEqual(other_close.status_code, status.HTTP_404_NOT_FOUND)

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


class JobApplicationAPITests(APITestCase):
    password = "A-strong-test-password-2026"
    resume_contents = b"%PDF-1.7\nOriginal resume"

    def setUp(self):
        self.temporary_media = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_media.cleanup)
        self.media_override = override_settings(MEDIA_ROOT=self.temporary_media.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)

        self.employer = User.objects.create_user(
            email="application-employer@example.com",
            password=self.password,
            role=User.Role.EMPLOYER,
        )
        self.other_employer = User.objects.create_user(
            email="other-application-employer@example.com",
            password=self.password,
            role=User.Role.EMPLOYER,
        )
        self.candidate = User.objects.create_user(
            email="application-candidate@example.com",
            password=self.password,
            role=User.Role.CANDIDATE,
        )
        self.job = Job.objects.create(
            employer=self.employer,
            title="Python Engineer",
            description="Build API services.",
            experience="3+ years",
            location="Remote",
            job_type=Job.JobType.FULL_TIME,
            status=Job.Status.ACTIVE,
        )
        self.apply_url = f"/api/jobs/{self.job.pk}/apply/"
        self.client.force_authenticate(self.candidate)

    def upload_resume(self, candidate=None, contents=None):
        candidate = candidate or self.candidate
        profile = candidate.candidate_profile
        profile.resume.save(
            "candidate-resume.pdf",
            SimpleUploadedFile(
                "candidate-resume.pdf",
                contents or self.resume_contents,
                content_type="application/pdf",
            ),
            save=True,
        )
        return profile

    def apply(self):
        self.upload_resume()
        return self.client.post(self.apply_url)

    def create_application(self, candidate, job, application_status):
        application = JobApplication.objects.create(
            candidate=candidate,
            job=job,
            status=application_status,
        )
        application.resume_snapshot.save(
            "test-resume.pdf",
            SimpleUploadedFile(
                "test-resume.pdf",
                self.resume_contents,
                content_type="application/pdf",
            ),
            save=True,
        )
        return application

    def test_candidate_application_captures_resume_snapshot(self):
        self.upload_resume()

        response = self.client.post(self.apply_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        application = JobApplication.objects.get()
        self.assertEqual(application.candidate, self.candidate)
        self.assertEqual(application.job, self.job)
        self.assertEqual(application.status, JobApplication.Status.APPLIED)
        self.assertEqual(response.data["candidate_id"], self.candidate.pk)
        self.assertIn("/api/applications/", response.data["resume_url"])
        application.resume_snapshot.open("rb")
        try:
            self.assertEqual(application.resume_snapshot.read(), self.resume_contents)
        finally:
            application.resume_snapshot.close()

        self.upload_resume(contents=b"%PDF-1.7\nUpdated resume")
        application.refresh_from_db()
        application.resume_snapshot.open("rb")
        try:
            self.assertEqual(application.resume_snapshot.read(), self.resume_contents)
        finally:
            application.resume_snapshot.close()

    def test_application_requires_resume_and_active_job(self):
        missing_resume = self.client.post(self.apply_url)
        self.assertEqual(missing_resume.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("resume", missing_resume.data["errors"])

        self.upload_resume()
        self.job.status = Job.Status.INACTIVE
        self.job.save(update_fields=("status",))
        inactive_job = self.client.post(self.apply_url)

        self.assertEqual(inactive_job.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("job", inactive_job.data["errors"])
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_duplicate_application_is_rejected(self):
        first = self.apply()
        second = self.client.post(self.apply_url)

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("job", second.data["errors"])
        self.assertEqual(JobApplication.objects.count(), 1)

    def test_only_candidates_can_apply(self):
        self.client.force_authenticate(self.employer)
        employer_response = self.client.post(self.apply_url)
        self.client.force_authenticate(user=None)
        anonymous_response = self.client.post(self.apply_url)

        self.assertEqual(employer_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(anonymous_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_candidate_tracks_own_applications_and_employer_updates_status(self):
        application_response = self.apply()
        application_id = application_response.data["id"]
        list_url = "/api/applications/"

        candidate_list = self.client.get(list_url)
        candidate_update = self.client.patch(
            f"{list_url}{application_id}/",
            {"status": JobApplication.Status.SHORTLISTED},
            format="json",
        )

        self.assertEqual(candidate_list.status_code, status.HTTP_200_OK)
        self.assertEqual(candidate_list.data["count"], 1)
        self.assertEqual(candidate_update.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.employer)
        employer_list = self.client.get(list_url)
        employer_update = self.client.patch(
            f"{list_url}{application_id}/",
            {"status": JobApplication.Status.SHORTLISTED},
            format="json",
        )

        self.assertEqual(employer_list.status_code, status.HTTP_200_OK)
        self.assertEqual(employer_list.data["count"], 1)
        self.assertEqual(employer_update.status_code, status.HTTP_200_OK)
        application = JobApplication.objects.get(pk=application_id)
        self.assertEqual(application.status, JobApplication.Status.SHORTLISTED)

    def test_employer_can_progress_application_and_status_changes_are_audited(self):
        response = self.apply()
        application_id = response.data["id"]
        application_url = f"/api/applications/{application_id}/"
        self.client.force_authenticate(self.employer)

        shortlisted = self.client.post(
            f"{application_url}shortlist/",
            {"note": "Experience matches the role."},
            format="json",
        )
        interview = self.client.post(
            f"{application_url}move-stage/",
            {
                "status": JobApplication.Status.INTERVIEW_SCHEDULED,
                "note": "Technical interview booked.",
            },
            format="json",
        )
        selected = self.client.patch(
            application_url,
            {
                "status": JobApplication.Status.SELECTED,
                "note": "Interview panel approved.",
            },
            format="json",
        )

        self.assertEqual(shortlisted.status_code, status.HTTP_200_OK)
        self.assertEqual(interview.status_code, status.HTTP_200_OK)
        self.assertEqual(selected.status_code, status.HTTP_200_OK)
        self.assertEqual(selected.data["status"], JobApplication.Status.SELECTED)
        history = selected.data["status_history"]
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0]["from_status"], None)
        self.assertEqual(history[0]["to_status"], JobApplication.Status.APPLIED)
        self.assertEqual(
            history[1]["action"],
            JobApplicationStatusHistory.Action.SHORTLISTED,
        )
        self.assertEqual(history[1]["changed_by_id"], self.employer.pk)
        self.assertEqual(history[1]["note"], "Experience matches the role.")
        self.assertEqual(
            history[2]["to_status"],
            JobApplication.Status.INTERVIEW_SCHEDULED,
        )
        self.assertEqual(history[3]["to_status"], JobApplication.Status.SELECTED)
        self.assertTrue(all(entry["created_at"] for entry in history))

        locked = self.client.post(
            f"{application_url}reject/",
            format="json",
        )
        self.assertEqual(locked.status_code, status.HTTP_400_BAD_REQUEST)
        application = JobApplication.objects.get(pk=application_id)
        self.assertEqual(application.status, JobApplication.Status.SELECTED)
        self.assertEqual(application.status_history.count(), 4)

    def test_invalid_stage_skips_and_rejected_applications_are_locked(self):
        response = self.apply()
        application_id = response.data["id"]
        application_url = f"/api/applications/{application_id}/"
        self.client.force_authenticate(self.employer)

        skipped_stage = self.client.patch(
            application_url,
            {"status": JobApplication.Status.INTERVIEW_SCHEDULED},
            format="json",
        )
        shortlisted = self.client.post(f"{application_url}shortlist/")
        rejected = self.client.post(
            f"{application_url}reject/",
            {"note": "Role requirements not met."},
            format="json",
        )
        locked = self.client.patch(
            application_url,
            {"status": JobApplication.Status.SHORTLISTED},
            format="json",
        )

        self.assertEqual(skipped_stage.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(shortlisted.status_code, status.HTTP_200_OK)
        self.assertEqual(rejected.status_code, status.HTTP_200_OK)
        self.assertEqual(locked.status_code, status.HTTP_400_BAD_REQUEST)
        application = JobApplication.objects.get(pk=application_id)
        self.assertEqual(application.status, JobApplication.Status.REJECTED)
        self.assertEqual(application.status_history.count(), 3)

    def test_employer_cannot_access_another_employers_application(self):
        response = self.apply()
        application_id = response.data["id"]
        self.client.force_authenticate(self.other_employer)

        detail = self.client.get(f"/api/applications/{application_id}/")
        status_update = self.client.patch(
            f"/api/applications/{application_id}/",
            {"status": JobApplication.Status.REJECTED},
            format="json",
        )

        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(status_update.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            JobApplication.objects.get(pk=application_id).status,
            JobApplication.Status.APPLIED,
        )

    def test_employer_can_filter_and_search_applicants_for_owned_job(self):
        matching_candidate = self.candidate
        matching_candidate.candidate_profile.experience = (
            "Five years of distributed systems experience."
        )
        matching_candidate.candidate_profile.save(update_fields=("experience",))
        shortlisted_application = self.create_application(
            matching_candidate,
            self.job,
            JobApplication.Status.SHORTLISTED,
        )
        other_candidate = User.objects.create_user(
            email="another-candidate@example.com",
            password=self.password,
            role=User.Role.CANDIDATE,
        )
        applied_application = self.create_application(
            other_candidate,
            self.job,
            JobApplication.Status.APPLIED,
        )
        self.client.force_authenticate(self.employer)

        response = self.client.get(
            f"/api/jobs/{self.job.pk}/applicants/",
            {"status": JobApplication.Status.SHORTLISTED, "search": "distributed"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            shortlisted_application.pk,
        )
        self.assertNotEqual(response.data["results"][0]["id"], applied_application.pk)

        invalid_status = self.client.get(
            f"/api/jobs/{self.job.pk}/applicants/",
            {"status": "not-a-stage"},
        )
        self.assertEqual(invalid_status.status_code, status.HTTP_400_BAD_REQUEST)

        other_job = Job.objects.create(
            employer=self.other_employer,
            title="Other role",
            description="Other job.",
            experience="Experience varies",
            location="Remote",
            job_type=Job.JobType.FULL_TIME,
            status=Job.Status.ACTIVE,
        )
        other_owner_request = self.client.get(
            f"/api/jobs/{other_job.pk}/applicants/"
        )
        self.assertEqual(other_owner_request.status_code, status.HTTP_404_NOT_FOUND)

    def test_employer_dashboard_and_job_analytics_are_scoped_and_count_stages(self):
        another_employer_job = Job.objects.create(
            employer=self.other_employer,
            title="Other role",
            description="Other job.",
            experience="Experience varies",
            location="Remote",
            job_type=Job.JobType.FULL_TIME,
            status=Job.Status.ACTIVE,
        )
        self.create_application(self.candidate, self.job, JobApplication.Status.APPLIED)
        self.create_application(
            User.objects.create_user(
                email="shortlisted-candidate@example.com",
                password=self.password,
                role=User.Role.CANDIDATE,
            ),
            self.job,
            JobApplication.Status.SHORTLISTED,
        )
        other_candidate = User.objects.create_user(
            email="other-employer-candidate@example.com",
            password=self.password,
            role=User.Role.CANDIDATE,
        )
        self.create_application(
            other_candidate,
            another_employer_job,
            JobApplication.Status.SHORTLISTED,
        )
        self.client.force_authenticate(self.employer)

        dashboard = self.client.get("/api/employer/dashboard/")
        analytics = self.client.get(f"/api/jobs/{self.job.pk}/analytics/")

        self.assertEqual(dashboard.status_code, status.HTTP_200_OK)
        self.assertEqual(dashboard.data["job_counts"]["total"], 1)
        self.assertEqual(dashboard.data["job_counts"]["active"], 1)
        self.assertEqual([job["id"] for job in dashboard.data["jobs"]], [self.job.pk])
        self.assertEqual(dashboard.data["applications"]["total"], 2)
        self.assertEqual(dashboard.data["applications"]["shortlist_ratio"], 50)
        self.assertEqual(analytics.status_code, status.HTTP_200_OK)
        self.assertEqual(analytics.data["applications"]["status_counts"]["applied"], 1)
        self.assertEqual(
            analytics.data["applications"]["status_counts"]["shortlisted"],
            1,
        )

        self.client.force_authenticate(self.candidate)
        forbidden_dashboard = self.client.get("/api/employer/dashboard/")
        forbidden_analytics = self.client.get(f"/api/jobs/{self.job.pk}/analytics/")
        self.assertEqual(forbidden_dashboard.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(forbidden_analytics.status_code, status.HTTP_403_FORBIDDEN)

    def test_resume_snapshot_is_downloadable_only_by_candidate_or_job_employer(self):
        response = self.apply()
        resume_url = response.data["resume_url"]

        candidate_download = self.client.get(resume_url)
        self.client.force_authenticate(self.employer)
        employer_download = self.client.get(resume_url)
        self.client.force_authenticate(self.other_employer)
        other_employer_download = self.client.get(resume_url)

        self.assertEqual(candidate_download.status_code, status.HTTP_200_OK)
        self.assertEqual(employer_download.status_code, status.HTTP_200_OK)
        self.assertEqual(other_employer_download.status_code, status.HTTP_404_NOT_FOUND)
        try:
            downloaded_contents = b"".join(candidate_download.streaming_content)
        finally:
            candidate_download.close()
            employer_download.close()
            other_employer_download.close()
        self.assertEqual(downloaded_contents, self.resume_contents)
