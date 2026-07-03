from django.contrib import admin

from apps.personnel.models import EmployeeProfile


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "employee_number", "position", "role", "leave_balance")
    list_filter = ("role",)
    search_fields = ("user__first_name", "user__last_name", "user__username")
