from django.contrib import admin

from apps.personnel.models import AnnualLeave, EmployeeProfile


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "employee_number", "position", "role", "leave_balance")
    list_filter = ("role",)
    search_fields = ("user__first_name", "user__last_name", "user__username")


@admin.register(AnnualLeave)
class AnnualLeaveAdmin(admin.ModelAdmin):
    list_display = ("employee", "year", "quota", "consumed", "remaining", "is_blocked")
    list_filter = ("year", "is_blocked")
    search_fields = ("employee__user__first_name", "employee__user__last_name", "employee__user__username")
    list_select_related = ("employee", "employee__user")

    @admin.display(description="Restant")
    def remaining(self, obj):
        return obj.quota - obj.consumed
