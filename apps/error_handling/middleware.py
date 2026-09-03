"""
Middleware global de gestion des exceptions.

- Capture toute exception non gérée
- Génère un identifiant d'erreur unique (ex: ERR-20260821-00125)
- Log structuré (fichier logs/application.log)
- Rendu de la page 500 professionnelle
- Option : notification IT pour les erreurs critiques
"""
import logging
import threading
import uuid
from datetime import datetime

from django.conf import settings
from django.shortcuts import render
from django.utils import timezone

logger = logging.getLogger("application")

CRITICAL_ERRORS = (
    "ImproperlyConfigured",
    "OperationalError",
    "DatabaseError",
)

# Thread-local storage so the DatabaseLogHandler can access the current
# request's user / path / method / IP when emitting records.
_request_context = threading.local()


def _get_request_context():
    """Return the current request context (or an empty dict) for the log handler."""
    return getattr(_request_context, "data", {}) or {}


def _generate_error_id():
    return f"ERR-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def _log_error(request, error_id, exception):
    user = getattr(request.user, "username", "anonyme") if request and hasattr(request, "user") else "anonyme"
    path = getattr(request, "path", "?") if request else "?"
    method = getattr(request, "method", "?") if request else "?"
    logger.error(
        "[%s] Erreur ID=%s | Utilisateur=%s | URL=%s | Méthode=%s | Exception=%s",
        timezone.now().isoformat(),
        error_id,
        user,
        path,
        method,
        exception,
        exc_info=True,
    )


def _is_critical(exception):
    return any(cls_name in type(exception).__name__ for cls_name in CRITICAL_ERRORS)


class GlobalExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Store request context in thread-local so the log handler can access it
        ip = _get_client_ip(request)
        _request_context.data = {
            "user": getattr(request, "user", None),
            "path": getattr(request, "path", ""),
            "method": getattr(request, "method", ""),
            "ip": ip,
        }
        try:
            response = self.get_response(request)
        finally:
            _request_context.data = {}
        return response

    def process_exception(self, request, exception):
        """Capture toutes les exceptions non gérées."""
        error_id = _generate_error_id()

        # 1. Journaliser
        _log_error(request, error_id, exception)

        # 2. Notifier l'IT en cas d'erreur critique uniquement
        if _is_critical(exception):
            try:
                from apps.error_handling.notifications import notify_it

                notify_it(error_id, request, exception)
            except Exception:
                logger.warning("Notification IT impossible pour %s", error_id)

        # 3. Rendre la page 500 professionnelle (template existant)
        context = {
            "error_id": error_id,
        }
        return render(
            request,
            "errors/500.html",
            context,
            status=500,
        )


def _get_client_ip(request):
    """Extract the client IP address from the request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "")
    return ip
