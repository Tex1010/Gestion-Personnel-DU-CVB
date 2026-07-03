from django.contrib import admin

from apps.requests_management.models import RecoveryLine, StaffRequest


class RecoveryLineInline(admin.TabularInline):
    model = RecoveryLine
    extra = 0


@admin.register(StaffRequest)
class StaffRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "request_type", "status", "start_date", "created_at")
    list_filter = ("request_type", "status")
    search_fields = ("employee__user__first_name", "employee__user__last_name")
    inlines = [RecoveryLineInline]
