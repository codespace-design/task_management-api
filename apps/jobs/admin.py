from django.contrib import admin

from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "employer", "job_type", "status", "created_at")
    list_filter = ("status", "job_type")
    search_fields = ("title", "description", "employer__email")
