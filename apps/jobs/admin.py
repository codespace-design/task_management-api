from django.contrib import admin

from .models import Job, JobApplication, JobApplicationStatusHistory


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


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "candidate", "job", "status", "applied_at")
    list_filter = ("status", "applied_at")
    search_fields = ("candidate__email", "job__title")
    readonly_fields = (
        "candidate",
        "job",
        "resume_snapshot",
        "status",
        "applied_at",
        "updated_at",
    )


@admin.register(JobApplicationStatusHistory)
class JobApplicationStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "application",
        "from_status",
        "to_status",
        "action",
        "changed_by",
        "created_at",
    )
    list_filter = ("action", "to_status", "created_at")
    search_fields = ("application__candidate__email", "application__job__title")
    readonly_fields = (
        "application",
        "from_status",
        "to_status",
        "action",
        "changed_by",
        "note",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
