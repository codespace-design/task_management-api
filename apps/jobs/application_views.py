from pathlib import Path

from django.http import FileResponse, Http404
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsEmployerOrAdmin

from .models import JobApplication, JobApplicationStatusHistory
from .pagination import JobPagination
from .serializers import JobApplicationSerializer, JobApplicationStatusSerializer
from .services import (
    InvalidStatusTransition,
    filter_applications,
    transition_application,
)


class JobApplicationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    pagination_class = JobPagination
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in {"partial_update", "shortlist", "reject", "move_stage"}:
            return [IsEmployerOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = JobApplication.objects.select_related(
            "candidate",
            "job",
            "job__employer",
        ).prefetch_related(
            "job__skill_entries",
            "status_history",
        )
        user = self.request.user
        if user.role == User.Role.CANDIDATE:
            return queryset.filter(candidate=user)
        if user.role == User.Role.EMPLOYER:
            return queryset.filter(job__employer=user)
        if user.role == User.Role.ADMIN:
            return queryset
        return queryset.none()

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        return filter_applications(queryset, self.request.query_params)

    def get_serializer_class(self):
        if self.action == "partial_update":
            return JobApplicationStatusSerializer
        return JobApplicationSerializer

    @action(detail=True, methods=["get"])
    def resume(self, request, pk=None):
        application = self.get_object()
        resume = application.resume_snapshot
        if not resume or not resume.storage.exists(resume.name):
            raise Http404

        response = FileResponse(
            resume.open("rb"),
            as_attachment=True,
            filename=f"resume{Path(resume.name).suffix}",
            content_type="application/octet-stream",
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def partial_update(self, request, *args, **kwargs):
        return self._transition_status(
            request,
            target_status=None,
            action=JobApplicationStatusHistory.Action.STATUS_CHANGED,
            allowed_fields={"status", "note"},
        )

    @action(detail=True, methods=["post"])
    def shortlist(self, request, pk=None):
        return self._transition_status(
            request,
            target_status=JobApplication.Status.SHORTLISTED,
            action=JobApplicationStatusHistory.Action.SHORTLISTED,
            allowed_fields={"note"},
        )

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._transition_status(
            request,
            target_status=JobApplication.Status.REJECTED,
            action=JobApplicationStatusHistory.Action.REJECTED,
            allowed_fields={"note"},
        )

    @action(detail=True, methods=["post"], url_path="move-stage")
    def move_stage(self, request, pk=None):
        return self._transition_status(
            request,
            target_status=None,
            action=JobApplicationStatusHistory.Action.STAGE_MOVED,
            allowed_fields={"status", "note"},
        )

    def _transition_status(self, request, target_status, action, allowed_fields):
        if set(request.data) - allowed_fields:
            raise ValidationError(
                {"detail": "Only status and note fields are accepted."}
            )
        serializer = JobApplicationStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if target_status is None:
            target_status = validated_data.get("status")
            if target_status is None:
                raise ValidationError({"status": "This field is required."})
        elif "status" in validated_data:
            raise ValidationError(
                {"status": "This action determines the application status."}
            )

        application = self.get_object()
        try:
            application = transition_application(
                application,
                target_status,
                request.user,
                note=validated_data.get("note", ""),
                action=action,
            )
        except InvalidStatusTransition as error:
            raise ValidationError({"status": str(error)}) from error

        return Response(
            JobApplicationSerializer(
                application,
                context=self.get_serializer_context(),
            ).data
        )
