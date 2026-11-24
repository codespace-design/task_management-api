from django.contrib import admin

from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "employer",
        "job_type",
        "status",
        "is_featured",
        "created_at",
    )
    list_filter = ("status", "is_featured", "job_type")
    search_fields = ("title", "description", "employer__email")
