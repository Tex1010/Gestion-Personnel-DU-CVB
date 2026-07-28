"""Custom error handler views for professional error pages."""

from django.shortcuts import render


def _error_view(request, template_name, status_code):
    """Render a professional error page with the given status code."""
    return render(request, template_name, status=status_code)


def bad_request_view(request, exception=None):
    """Handle 400 - Bad Request errors."""
    return _error_view(request, "errors/400.html", 400)


def permission_denied_view(request, exception=None):
    """Handle 403 - Forbidden errors."""
    return _error_view(request, "errors/403.html", 403)


def page_not_found_view(request, exception=None):
    """Handle 404 - Page Not Found errors."""
    return _error_view(request, "errors/404.html", 404)


def server_error_view(request):
    """Handle 500 - Internal Server Error."""
    return _error_view(request, "errors/500.html", 500)
