from datetime import datetime, time, timedelta

from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import User
from apps.accounts.permissions import IsEmployerOrAdmin

from .models import Task
from .pagination import TaskPagination
from .serializers import TaskSerializer


def task_dashboard(request):
    return render(request, "tasks/dashboard.html")


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.select_related("created_by").all()
    serializer_class = TaskSerializer
    pagination_class = TaskPagination
    filter_backends = [SearchFilter]
    search_fields = ["title", "description"]

    def get_queryset(self):
        queryset = Task.objects.select_related("created_by").all()
        if (
            self.action in {"update", "partial_update", "destroy"}
            and self.request.user.role != User.Role.ADMIN
        ):
            queryset = queryset.filter(created_by=self.request.user)
        return queryset

    def filter_queryset(self, queryset):
        if self.action != "list":
            return queryset

        params = self.request.query_params
        role = params.get("role")
        if role:
            if role not in User.Role.values:
                raise ValidationError(
                    {"role": f"Choose one of: {', '.join(User.Role.values)}."}
                )
            queryset = queryset.filter(created_by__role=role)

        status_value = params.get("status")
        statuses = {"completed": True, "pending": False}
        if status_value:
            if status_value not in statuses:
                raise ValidationError(
                    {"status": "Choose either 'completed' or 'pending'."}
                )
            queryset = queryset.filter(completed=statuses[status_value])

        after = self._parse_date_param(params.get("created_after"), "created_after")
        before = self._parse_date_param(params.get("created_before"), "created_before")
        if after and before and after > before:
            raise ValidationError(
                {"created_before": "Must be on or after created_after."}
            )
        if after:
            start = timezone.make_aware(
                datetime.combine(after, time.min),
                timezone.get_current_timezone(),
            )
            queryset = queryset.filter(created_at__gte=start)
        if before:
            end = timezone.make_aware(
                datetime.combine(before + timedelta(days=1), time.min),
                timezone.get_current_timezone(),
            )
            queryset = queryset.filter(created_at__lt=end)

        return super().filter_queryset(queryset)

    @staticmethod
    def _parse_date_param(value, parameter):
        if value is None:
            return None
        parsed = parse_date(value)
        if parsed is None:
            raise ValidationError({parameter: "Use the YYYY-MM-DD date format."})
        return parsed

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            permission_classes = [IsEmployerOrAdmin]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
