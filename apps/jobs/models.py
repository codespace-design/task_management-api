from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


def application_resume_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"application-resumes/{instance.candidate_id}/{uuid4().hex}{extension}"


class Job(models.Model):
    class JobType(models.TextChoices):
        FULL_TIME = "full_time", "Full-time"
        PART_TIME = "part_time", "Part-time"
        CONTRACT = "contract", "Contract"
        INTERNSHIP = "internship", "Internship"
        TEMPORARY = "temporary", "Temporary"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=255, db_index=True)
    experience = models.CharField(max_length=255)
    minimum_experience_years = models.PositiveSmallIntegerField(null=True, blank=True)
    maximum_experience_years = models.PositiveSmallIntegerField(null=True, blank=True)
    minimum_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    maximum_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    job_type = models.CharField(max_length=20, choices=JobType.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    is_featured = models.BooleanField(default=False)
    employer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="jobs",
        limit_choices_to={"role": "employer"},
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["status", "-created_at"],
                name="job_status_created_idx",
            ),
            models.Index(
                fields=["employer", "status"],
                name="job_employer_status_idx",
            ),
            models.Index(
                fields=["status", "is_featured", "-created_at"],
                name="job_featured_latest_idx",
            ),
            models.Index(
                fields=["status", "job_type"],
                name="job_status_type_idx",
            ),
            models.Index(
                fields=["status", "minimum_salary"],
                name="job_status_min_salary_idx",
            ),
            models.Index(
                fields=["status", "maximum_salary"],
                name="job_status_max_salary_idx",
            ),
            models.Index(
                fields=["status", "minimum_experience_years"],
                name="job_status_min_exp_idx",
            ),
            models.Index(
                fields=["status", "maximum_experience_years"],
                name="job_status_max_exp_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(minimum_salary__isnull=True)
                    | Q(maximum_salary__isnull=True)
                    | Q(minimum_salary__lte=F("maximum_salary"))
                ),
                name="job_salary_range_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(minimum_experience_years__isnull=True)
                    | Q(maximum_experience_years__isnull=True)
                    | Q(
                        minimum_experience_years__lte=F(
                            "maximum_experience_years"
                        )
                    )
                ),
                name="job_experience_range_valid",
            ),
        ]

    def __str__(self):
        return self.title


class JobSkill(models.Model):
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="skill_entries",
    )
    name = models.CharField(max_length=80)
    normalized_name = models.CharField(max_length=80)

    class Meta:
        ordering = ["normalized_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "normalized_name"],
                name="jobskill_job_normalized_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["normalized_name", "job"],
                name="jobskill_name_job_idx",
            ),
        ]

    def __str__(self):
        return self.name


class JobApplication(models.Model):
    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        SHORTLISTED = "shortlisted", "Shortlisted"
        INTERVIEW_SCHEDULED = "interview_scheduled", "Interview scheduled"
        REJECTED = "rejected", "Rejected"
        SELECTED = "selected", "Selected"

    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="job_applications",
        limit_choices_to={"role": "candidate"},
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    resume_snapshot = models.FileField(upload_to=application_resume_upload_path)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.APPLIED,
        db_index=True,
    )
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "job"],
                name="jobapplication_candidate_job_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["candidate", "-applied_at"],
                name="jobapp_candidate_date_idx",
            ),
            models.Index(
                fields=["job", "status", "-applied_at"],
                name="jobapp_job_status_date_idx",
            ),
        ]

    def __str__(self):
        return f"{self.candidate} applied for {self.job}"


class JobApplicationStatusHistory(models.Model):
    class Action(models.TextChoices):
        APPLICATION_SUBMITTED = "application_submitted", "Application submitted"
        SHORTLISTED = "shortlisted", "Candidate shortlisted"
        REJECTED = "rejected", "Candidate rejected"
        STAGE_MOVED = "stage_moved", "Candidate moved between stages"
        STATUS_CHANGED = "status_changed", "Status changed"

    application = models.ForeignKey(
        JobApplication,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    from_status = models.CharField(
        max_length=30,
        choices=JobApplication.Status.choices,
        blank=True,
        null=True,
    )
    to_status = models.CharField(
        max_length=30,
        choices=JobApplication.Status.choices,
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="application_status_changes",
        blank=True,
        null=True,
    )
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["application", "created_at"],
                name="jobapp_history_date_idx",
            ),
        ]

    def __str__(self):
        return f"{self.application_id}: {self.from_status} -> {self.to_status}"
