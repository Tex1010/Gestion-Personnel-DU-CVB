from django.contrib import admin

from apps.administration.models import LoginBranding


@admin.register(LoginBranding)
class LoginBrandingAdmin(admin.ModelAdmin):
    list_display = ("site_name", "email", "updated_at")
