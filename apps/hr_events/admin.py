from django.contrib import admin

from apps.hr_events.models import HREvent


@admin.register(HREvent)
class HREventAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "event_type",
        "status",
        "days",
        "start_date",
        "end_date",
        "created_at",
        "created_by",
    )
    list_filter = ("event_type", "status", "created_at")
    search_fields = (
        "employee__user__first_name",
        "employee__user__last_name",
        "employee__user__username",
        "reason",
    )
    list_select_related = ("employee", "employee__user", "created_by")
    readonly_fields = ("created_at", "updated_at", "created_by")
    date_hierarchy = "created_at"
