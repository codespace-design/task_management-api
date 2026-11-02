from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TaskViewSet, task_dashboard

router = DefaultRouter()
router.register(r"tasks", TaskViewSet, basename="task")

urlpatterns = [
    path("", task_dashboard, name="task-dashboard"),
    path("", include(router.urls)),
]
