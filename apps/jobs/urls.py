from django.urls import path
from rest_framework.routers import DefaultRouter

from .application_views import JobApplicationViewSet
from .views import EmployerDashboardView, JobViewSet

router = DefaultRouter()
router.register("jobs", JobViewSet, basename="job")
router.register("applications", JobApplicationViewSet, basename="application")

urlpatterns = [
    path(
        "employer/dashboard/",
        EmployerDashboardView.as_view(),
        name="employer-dashboard",
    ),
    *router.urls,
]
