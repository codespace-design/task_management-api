from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User

from .models import Job
from .permissions import IsEmployerOwnerOrReadOnly
from .serializers import JobSerializer


class JobViewSet(viewsets.ModelViewSet):
    serializer_class = JobSerializer
    permission_classes = [IsEmployerOwnerOrReadOnly]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        queryset = Job.objects.select_related("employer").all()
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()
        if user.role == User.Role.EMPLOYER:
            return queryset.filter(employer=user)
        if user.role == User.Role.CANDIDATE:
            return queryset.filter(status=Job.Status.ACTIVE)
        return queryset

    def perform_create(self, serializer):
        serializer.save(employer=self.request.user)

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
