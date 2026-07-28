from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("api/mobile/", include("apps.mobile_api.urls")),
    path("", include("apps.personnel.urls")),
    path("demandes/", include("apps.requests_management.urls")),
    path("admin-metier/", include("apps.administration.urls")),
    path("admin-metier/", include("apps.hr_events.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom error handlers - professional error pages
handler400 = "config.errors.bad_request_view"
handler403 = "config.errors.permission_denied_view"
handler404 = "config.errors.page_not_found_view"
handler500 = "config.errors.server_error_view"
