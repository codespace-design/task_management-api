from django.shortcuts import render
from rest_framework import viewsets

from .models import Task
from .serializers import TaskSerializer


def task_dashboard(request):
    return render(request, "tasks/dashboard.html")


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
