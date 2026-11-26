from decimal import Decimal, InvalidOperation

from django.db.models import Exists, OuterRef, Q
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import CandidateProfile, User
from apps.accounts.permissions import IsCandidate, IsEmployer, IsEmployerOrAdmin

from .models import Job, JobApplication, JobSkill
from .pagination import JobPagination
from .permissions import IsEmployerOwnerOrReadOnly
from .serializers import JobApplicationSerializer, JobSerializer
from .services import (
    DuplicateApplication,
    ResumeUnavailable,
    application_status_summary,
    create_job_application,
    filter_applications,
)


class JobViewSet(viewsets.ModelViewSet):
    serializer_class = JobSerializer
    pagination_class = JobPagination
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_permissions(self):
        if self.action == "apply":
            return [IsCandidate()]
        if self.action in {"applicants", "analytics"}:
            return [IsEmployerOrAdmin()]
        if self.action in {"list", "retrieve", "featured", "latest"}:
            return [AllowAny()]
        return [IsEmployerOwnerOrReadOnly()]

    def get_queryset(self):
        queryset = Job.objects.select_related("employer").prefetch_related(
            "skill_entries"
        )
        user = self.request.user
        if self.action in {"featured", "latest"} or not user.is_authenticated:
            return queryset.filter(status=Job.Status.ACTIVE)
        if self.action == "apply":
            return queryset
        if user.role == User.Role.EMPLOYER:
            return queryset.filter(employer=user)
        if user.role == User.Role.CANDIDATE:
            return queryset.filter(status=Job.Status.ACTIVE)
        return queryset

    def filter_queryset(self, queryset):
        params = self.request.query_params
        search = params.get("search", "").strip()
        if len(search) > 200:
            raise ValidationError({"search": "Must be 200 characters or fewer."})
        for index, term in enumerate(search.split()):
            matching_skill = JobSkill.objects.filter(
                job_id=OuterRef("pk"),
                name__icontains=term,
            )
            matching_skill_alias = f"skill_match_{index}"
            queryset = queryset.annotate(
                **{matching_skill_alias: Exists(matching_skill)}
            ).filter(
                Q(title__icontains=term)
                | Q(description__icontains=term)
                | Q(location__icontains=term)
                | Q(experience__icontains=term)
                | Q(**{matching_skill_alias: True})
            )

        skill = params.get("skill", "").strip()
        if skill:
            if len(skill) > 80:
                raise ValidationError({"skill": "Must be 80 characters or fewer."})
            queryset = queryset.filter(skill_entries__normalized_name=skill.casefold())

        location = params.get("location", "").strip()
        if location:
            queryset = queryset.filter(location__icontains=location)

        job_type = params.get("job_type")
        if job_type:
            if job_type not in Job.JobType.values:
                raise ValidationError(
                    {"job_type": f"Choose one of: {', '.join(Job.JobType.values)}."}
                )
            queryset = queryset.filter(job_type=job_type)

        minimum_experience = self._parse_integer(
            params.get("min_experience_years"),
            "min_experience_years",
        )
        maximum_experience = self._parse_integer(
            params.get("max_experience_years"),
            "max_experience_years",
        )
        if (
            minimum_experience is not None
            and maximum_experience is not None
            and minimum_experience > maximum_experience
        ):
            raise ValidationError(
                {"max_experience_years": "Must be on or above min_experience_years."}
            )
        if minimum_experience is not None:
            queryset = queryset.filter(
                Q(maximum_experience_years__gte=minimum_experience)
                | Q(maximum_experience_years__isnull=True)
            )
        if maximum_experience is not None:
            queryset = queryset.filter(
                Q(minimum_experience_years__lte=maximum_experience)
                | Q(minimum_experience_years__isnull=True)
            )

        minimum_salary = self._parse_decimal(params.get("min_salary"), "min_salary")
        maximum_salary = self._parse_decimal(params.get("max_salary"), "max_salary")
        if (
            minimum_salary is not None
            and maximum_salary is not None
            and minimum_salary > maximum_salary
        ):
            raise ValidationError({"max_salary": "Must be on or above min_salary."})
        if minimum_salary is not None:
            queryset = queryset.filter(
                Q(maximum_salary__gte=minimum_salary)
                | Q(maximum_salary__isnull=True)
            )
        if maximum_salary is not None:
            queryset = queryset.filter(
                Q(minimum_salary__lte=maximum_salary)
                | Q(minimum_salary__isnull=True)
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(employer=self.request.user)

    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        job = self.get_object()
        if job.status != Job.Status.ACTIVE:
            raise ValidationError(
                {"job": "Applications are only accepted for active jobs."}
            )

        profile = CandidateProfile.objects.filter(
            user=request.user,
            is_active=True,
        ).first()
        if (
            profile is None
            or not profile.resume
            or not profile.resume.storage.exists(profile.resume.name)
        ):
            raise ValidationError(
                {
                    "resume": (
                        "Upload a resume to your active candidate profile before "
                        "applying."
                    )
                }
            )

        try:
            application = create_job_application(
                candidate=request.user,
                job=job,
                resume=profile.resume,
            )
        except DuplicateApplication as error:
            raise ValidationError(
                {"job": "You have already applied for this job."}
            ) from error
        except ResumeUnavailable as error:
            raise ValidationError(
                {"resume": "The profile resume could not be read; upload it again."}
            ) from error

        return Response(
            JobApplicationSerializer(
                application,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def featured(self, request):
        queryset = self.filter_queryset(self.get_queryset().filter(is_featured=True))
        return self._paginated_response(queryset)

    @action(detail=False, methods=["get"])
    def latest(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        return self._paginated_response(queryset)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        job = self.get_object()
        job.status = Job.Status.ACTIVE
        job.save(update_fields=("status", "updated_at"))
        return Response(self.get_serializer(job).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        job = self.get_object()
        job.status = Job.Status.INACTIVE
        job.save(update_fields=("status", "updated_at"))
        return Response(self.get_serializer(job).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        job = self.get_object()
        job.status = Job.Status.INACTIVE
        job.save(update_fields=("status", "updated_at"))
        return Response(self.get_serializer(job).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def applicants(self, request, pk=None):
        job = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(request, job)
        queryset = JobApplication.objects.filter(job=job).select_related(
            "candidate",
            "job",
            "job__employer",
        ).prefetch_related("job__skill_entries", "status_history")
        queryset = filter_applications(queryset, request.query_params)
        page = self.paginate_queryset(queryset)
        serializer = JobApplicationSerializer(
            page if page is not None else queryset,
            many=True,
            context=self.get_serializer_context(),
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        job = self.get_object()
        summary = application_status_summary(
            JobApplication.objects.filter(job=job)
        )
        return Response({"job_id": job.pk, "applications": summary})

    def _paginated_response(self, queryset):
        page = self.paginate_queryset(queryset)
        if page is not None:
            data = self.get_serializer(page, many=True).data
            return self.get_paginated_response(data)
        return Response(self.get_serializer(queryset, many=True).data)

    @staticmethod
    def _parse_integer(value, parameter):
        if value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise ValidationError({parameter: "Enter a whole number."}) from error
        if parsed < 0:
            raise ValidationError({parameter: "Must be zero or greater."})
        return parsed

    @staticmethod
    def _parse_decimal(value, parameter):
        if value is None:
            return None
        try:
            parsed = Decimal(value)
        except (InvalidOperation, TypeError, ValueError) as error:
            raise ValidationError({parameter: "Enter a valid number."}) from error
        if not parsed.is_finite() or parsed < 0:
            raise ValidationError(
                {parameter: "Must be a finite number zero or greater."}
            )
        return parsed


class EmployerDashboardView(APIView):
    permission_classes = [IsEmployer]

    def get(self, request):
        jobs = Job.objects.filter(employer=request.user).order_by("-created_at", "-id")
        job_counts = {
            "total": jobs.count(),
            "active": jobs.filter(status=Job.Status.ACTIVE).count(),
            "draft": jobs.filter(status=Job.Status.DRAFT).count(),
            "inactive": jobs.filter(status=Job.Status.INACTIVE).count(),
        }
        applications = JobApplication.objects.filter(job__employer=request.user)
        return Response(
            {
                "job_counts": job_counts,
                "applications": application_status_summary(applications),
                "jobs": JobSerializer(
                    jobs,
                    many=True,
                    context={"request": request},
                ).data,
            }
        )
