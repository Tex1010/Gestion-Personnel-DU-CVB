"""
Service métier centralisé pour les notifications intelligentes.

Logique :
- Chaque action importante du workflow génère une notification.
- Anti-doublon via event_key unique.
- Les notifications sont liées à un utilisateur (recipient).
- Priorités : info, warning, important.
"""

from django.urls import reverse

from apps.administration.models import Notification


def _create_notification(
    recipient,
    title,
    message,
    notification_type,
    priority=Notification.PRIORITY_INFO,
    link_url="",
    request_item=None,
    event_key="",
):
    """
    Crée une notification si elle n'existe pas déjà (anti-doublon).

    Retourne la notification créée ou None si elle existait déjà.
    """
    if not recipient:
        return None

    if not event_key:
        event_key = f"{notification_type}:{recipient.id}:{request_item.id if request_item else 'none'}"

    notification, created = Notification.objects.get_or_create(
        event_key=event_key,
        defaults={
            "recipient": recipient,
            "title": title,
            "message": message,
            "priority": priority,
            "notification_type": notification_type,
            "link_url": link_url,
            "request": request_item,
        },
    )
    return notification if created else None


def _get_request_link(request_item):
    """Retourne le lien vers la demande concernée."""
    if not request_item:
        return ""
    return reverse("administration:requests")


def _get_request_period_label(request_item):
    """Retourne une description lisible de la période de la demande."""
    if not request_item:
        return ""
    if request_item.start_date:
        start = request_item.start_date.strftime("%d/%m/%Y")
        if request_item.end_date and request_item.end_date != request_item.start_date:
            end = request_item.end_date.strftime("%d/%m/%Y")
            return f"du {start} au {end}"
        return f"du {start}"
    return request_item.period_label or ""


def _get_request_type_label(request_item):
    """Retourne le libellé du type de demande."""
    if not request_item:
        return "demande"
    return request_item.type_label.lower()


def notify_request_created(request_item, validators):
    """
    Notifie les validateurs concernés qu'une nouvelle demande nécessite leur validation.

    `validators` : liste d'utilisateurs (User) devant valider la demande.
    """
    if not request_item:
        return

    employee_name = request_item.employee.display_name
    request_type = _get_request_type_label(request_item)
    period = _get_request_period_label(request_item)
    link = _get_request_link(request_item)

    for validator in validators:
        if not validator or validator.id == request_item.employee.user_id:
            continue
        _create_notification(
            recipient=validator,
            title=f"Nouvelle demande de {request_type}",
            message=(
                f"Une nouvelle demande de {request_type} de {employee_name} "
                f"{period} nécessite votre validation."
            ),
            notification_type=Notification.TYPE_REQUEST_CREATED,
            priority=Notification.PRIORITY_IMPORTANT,
            link_url=link,
            request_item=request_item,
            event_key=f"created:{request_item.id}:{validator.id}",
        )


def notify_request_approved(request_item):
    """Notifie l'employé que sa demande a été acceptée."""
    if not request_item:
        return

    employee = request_item.employee.user
    request_type = _get_request_type_label(request_item)
    period = _get_request_period_label(request_item)
    link = _get_request_link(request_item)

    _create_notification(
        recipient=employee,
        title=f"Demande de {request_type} acceptée",
        message=f"Votre demande de {request_type} {period} a été acceptée.",
        notification_type=Notification.TYPE_REQUEST_APPROVED,
        priority=Notification.PRIORITY_INFO,
        link_url=link,
        request_item=request_item,
        event_key=f"approved:{request_item.id}:{employee.id}",
    )


def notify_request_rejected(request_item, comment=""):
    """Notifie l'employé que sa demande a été refusée."""
    if not request_item:
        return

    employee = request_item.employee.user
    request_type = _get_request_type_label(request_item)
    period = _get_request_period_label(request_item)
    link = _get_request_link(request_item)

    message = f"Votre demande de {request_type} {period} a été refusée."
    if comment:
        message += f" Motif : {comment}"

    _create_notification(
        recipient=employee,
        title=f"Demande de {request_type} refusée",
        message=message,
        notification_type=Notification.TYPE_REQUEST_REJECTED,
        priority=Notification.PRIORITY_IMPORTANT,
        link_url=link,
        request_item=request_item,
        event_key=f"rejected:{request_item.id}:{employee.id}",
    )


def notify_request_cancelled(request_item):
    """Notifie l'employé que sa demande a été annulée."""
    if not request_item:
        return

    employee = request_item.employee.user
    request_type = _get_request_type_label(request_item)
    period = _get_request_period_label(request_item)
    link = _get_request_link(request_item)

    _create_notification(
        recipient=employee,
        title=f"Demande de {request_type} annulée",
        message=f"Votre demande de {request_type} {period} a été annulée.",
        notification_type=Notification.TYPE_REQUEST_CANCELLED,
        priority=Notification.PRIORITY_INFO,
        link_url=link,
        request_item=request_item,
        event_key=f"cancelled:{request_item.id}:{employee.id}",
    )


def notify_request_stage_advanced(request_item, next_validator):
    """
    Notifie le validateur suivant qu'une demande est arrivée à son étape.

    `next_validator` : utilisateur (User) devant valider à l'étape suivante.
    """
    if not request_item or not next_validator:
        return

    employee_name = request_item.employee.display_name
    request_type = _get_request_type_label(request_item)
    period = _get_request_period_label(request_item)
    link = _get_request_link(request_item)

    _create_notification(
        recipient=next_validator,
        title=f"Demande de {request_type} nécessitant votre validation",
        message=(
            f"Une demande de {request_type} de {employee_name} {period} "
            f"nécessite votre validation."
        ),
        notification_type=Notification.TYPE_REQUEST_STAGE_ADVANCED,
        priority=Notification.PRIORITY_IMPORTANT,
        link_url=link,
        request_item=request_item,
        event_key=f"stage:{request_item.id}:{next_validator.id}",
    )


def notify_recovery_limit_reached(profile, year, limit):
    """Notifie l'employé que sa limite annuelle de récupération est atteinte."""
    if not profile:
        return

    _create_notification(
        recipient=profile.user,
        title=f"Limite de récupération {year} atteinte",
        message=(
            f"Vous avez atteint votre limite annuelle de récupération de {limit} jours "
            f"pour {year}. Vous devez effectuer une demande d'absence afin de consommer "
            f"votre récupération."
        ),
        notification_type=Notification.TYPE_RECOVERY_LIMIT_REACHED,
        priority=Notification.PRIORITY_IMPORTANT,
        event_key=f"limit_reached:{profile.id}:{year}",
    )


def notify_recovery_limit_near(profile, year, current, limit):
    """Notifie l'employé qu'il approche de sa limite annuelle de récupération."""
    if not profile:
        return

    _create_notification(
        recipient=profile.user,
        title=f"Récupération {year} presque au maximum",
        message=(
            f"Votre récupération {year} est de {current}/{limit} jours. "
            f"Vous approchez de la limite annuelle."
        ),
        notification_type=Notification.TYPE_RECOVERY_LIMIT_NEAR,
        priority=Notification.PRIORITY_WARNING,
        event_key=f"limit_near:{profile.id}:{year}",
    )