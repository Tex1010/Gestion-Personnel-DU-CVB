"""
Notifications IT pour les erreurs critiques uniquement.

Évite le spam : seulement :
- 500 non gérées
- DatabaseError / OperationalError
- toute exception critique
"""
import logging

from django.conf import settings

logger = logging.getLogger("application.notifications")

# Notifieur simple — à remplacer par votre canal préféré (email, Slack, webhook…)
def notify_it(error_id, request, exception):
    """Envoyer une notification IT pour une erreur critique."""
    try:
        admin_email = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", None)
        if not admin_email:
            return

        from django.core.mail import send_mail

        subject = f"[{error_id}] Erreur critique application"
        message = (
            f"Erreur ID : {error_id}\n"
            f"Utilisateur : {getattr(request.user, 'username', 'anonyme')}\n"
            f"URL : {getattr(request, 'path', '?')}\n"
            f"Méthode : {getattr(request, 'method', '?')}\n"
            f"Exception : {exception}\n"
        )
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [admin_email],
            fail_silently=True,
        )
    except Exception as notify_exception:
        logger.warning("Impossible d'envoyer la notification IT : %s", notify_exception)