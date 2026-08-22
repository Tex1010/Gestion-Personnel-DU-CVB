"""
Middleware global de gestion des exceptions.

- Capture toute exception non gérée
- Génère un identifiant d'erreur unique (ex: ERR-20260821-00125)
- Log structuré (fichier logs/application.log)
- Rendu de la page 500 professionnelle
- Option : notification IT pour les erreurs critiques
"""
import logging
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


def _generate_error_id():
    return f"ERR-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def _log_error(request, error_id, exception):
    logger.error(
        "[%s] Erreur ID=%s | Utilisateur=%s | URL=%s | Méthode=%s | Exception=%s",
        timezone.now().isoformat(),
        error_id,
        getattr(request.user, "username", "anonyme"),
        getattr(request, "path", "?"),
        getattr(request, "method", "?"),
        exception,
        exc_info=True,
    )


def _is_critical(exception):
    return any(cls_name in type(exception).__name__ for cls_name in CRITICAL_ERRORS)


class GlobalExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

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

        # 3. Rendre la page 500 professionnelle
        context = {
            "error_id": error_id,
        }
        return render(
            request,
            "error_handling/500.html",
            context,
            status=500,
        )
