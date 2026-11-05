from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsEmployerOrAdmin

from .models import Task
from .serializers import TaskSerializer


def task_dashboard(request):
    return render(request, "tasks/dashboard.html")


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            permission_classes = [IsEmployerOrAdmin]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
