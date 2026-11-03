"""Project URL configuration."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.accounts.urls")),
    path("", include("apps.tasks.urls")),
    path("api/", include("apps.tasks.urls")),
]
