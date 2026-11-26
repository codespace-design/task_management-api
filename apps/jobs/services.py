from pathlib import Path

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from rest_framework.exceptions import ValidationError

from .models import JobApplication, JobApplicationStatusHistory


class DuplicateApplication(Exception):
    """Raised when a candidate has already applied for a job."""


class ResumeUnavailable(Exception):
    """Raised when the candidate's current resume cannot be copied."""


class InvalidStatusTransition(Exception):
    """Raised when an application status change violates the workflow."""


ALLOWED_STATUS_TRANSITIONS = {
    JobApplication.Status.APPLIED: {
        JobApplication.Status.SHORTLISTED,
        JobApplication.Status.REJECTED,
    },
    JobApplication.Status.SHORTLISTED: {
        JobApplication.Status.INTERVIEW_SCHEDULED,
        JobApplication.Status.REJECTED,
    },
    JobApplication.Status.INTERVIEW_SCHEDULED: {
        JobApplication.Status.SHORTLISTED,
        JobApplication.Status.REJECTED,
        JobApplication.Status.SELECTED,
    },
}


def filter_applications(queryset, params):
    status_filter = params.get("status", "").strip()
    if status_filter:
        if status_filter not in JobApplication.Status.values:
            raise ValidationError(
                {"status": f"Choose one of: {', '.join(JobApplication.Status.values)}."}
            )
        queryset = queryset.filter(status=status_filter)

    search = params.get("search", "").strip()
    if len(search) > 200:
        raise ValidationError({"search": "Must be 200 characters or fewer."})
    if search:
        queryset = queryset.filter(
            Q(candidate__email__icontains=search)
            | Q(candidate__first_name__icontains=search)
            | Q(candidate__last_name__icontains=search)
            | Q(candidate__candidate_profile__education__icontains=search)
            | Q(candidate__candidate_profile__experience__icontains=search)
        )

    job_id = params.get("job_id", "").strip()
    if job_id:
        try:
            parsed_job_id = int(job_id)
        except ValueError as error:
            raise ValidationError({"job_id": "Enter a valid job ID."}) from error
        if parsed_job_id < 1:
            raise ValidationError({"job_id": "Enter a valid job ID."})
        queryset = queryset.filter(job_id=parsed_job_id)

    return queryset


def application_status_summary(queryset):
    status_counts = {status: 0 for status in JobApplication.Status.values}
    for row in queryset.values("status").annotate(count=Count("id")):
        status_counts[row["status"]] = row["count"]

    total = sum(status_counts.values())
    shortlisted = status_counts[JobApplication.Status.SHORTLISTED]
    return {
        "total": total,
        "status_counts": status_counts,
        "shortlisted": shortlisted,
        "shortlist_ratio": round(shortlisted * 100 / total, 2) if total else 0,
    }


def create_job_application(candidate, job, resume):
    try:
        with transaction.atomic():
            if JobApplication.objects.filter(candidate=candidate, job=job).exists():
                raise DuplicateApplication

            try:
                resume.open("rb")
                try:
                    resume_contents = resume.read()
                finally:
                    resume.close()
            except OSError as error:
                raise ResumeUnavailable from error

            application = JobApplication.objects.create(
                candidate=candidate,
                job=job,
            )
            application.resume_snapshot.save(
                Path(resume.name).name,
                ContentFile(resume_contents),
                save=True,
            )
            JobApplicationStatusHistory.objects.create(
                application=application,
                to_status=JobApplication.Status.APPLIED,
                action=JobApplicationStatusHistory.Action.APPLICATION_SUBMITTED,
                changed_by=candidate,
            )
            return application
    except IntegrityError as error:
        if JobApplication.objects.filter(candidate=candidate, job=job).exists():
            raise DuplicateApplication from error
        raise


@transaction.atomic
def transition_application(application, target_status, actor, note="", action=None):
    application = JobApplication.objects.select_for_update().get(pk=application.pk)
    allowed_statuses = ALLOWED_STATUS_TRANSITIONS.get(application.status, set())
    if target_status not in allowed_statuses:
        if application.status in {
            JobApplication.Status.REJECTED,
            JobApplication.Status.SELECTED,
        }:
            reason = f"Applications in the {application.status} stage are locked."
        else:
            reason = (
                f"Cannot move an application from {application.status} "
                f"to {target_status}."
            )
        raise InvalidStatusTransition(reason)

    previous_status = application.status
    application.status = target_status
    application.save(update_fields=("status", "updated_at"))
    if action is None:
        action = {
            JobApplication.Status.SHORTLISTED: (
                JobApplicationStatusHistory.Action.SHORTLISTED
            ),
            JobApplication.Status.REJECTED: (
                JobApplicationStatusHistory.Action.REJECTED
            ),
        }.get(target_status, JobApplicationStatusHistory.Action.STATUS_CHANGED)
    JobApplicationStatusHistory.objects.create(
        application=application,
        from_status=previous_status,
        to_status=target_status,
        action=action,
        changed_by=actor,
        note=note,
    )
    return application
