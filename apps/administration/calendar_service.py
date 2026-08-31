"""
Service centralisé de lecture des événements du calendrier.

Ce service est la SEULE source de vérité pour la lecture des événements
affichés dans le calendrier. Il lit UNIQUEMENT les données existantes
(StaffRequest, RecoveryLine, HREvent) et ne crée aucune donnée.

Principes :
- Congés et absences : plage start_date -> end_date des StaffRequest.
- Récupérations : lignes RecoveryLine (work_date) rattachées aux StaffRequest.
- Événements RH : familiaux, repos médical, absences maladie (HREvent).
- Seuls les statuts "submitted" et "approved" sont affichés pour les demandes.
- Les événements RH actifs sont toujours affichés.
- Les jours fériés connus par l'application (RecoveryLine.is_holiday=True)
  sont mis en évidence.
"""

from datetime import date, timedelta

from apps.hr_events.models import HREvent
from apps.requests_management.models import RecoveryLine, StaffRequest

EVENT_TYPE_LEAVE = "leave"
EVENT_TYPE_ABSENCE = "absence"
EVENT_TYPE_RECOVERY = "recovery"
EVENT_TYPE_FAMILY_EVENT = "family_event"
EVENT_TYPE_MEDICAL_LEAVE = "medical_leave"
EVENT_TYPE_SICK_ABSENCE = "sick_absence"


def _iter_date_range(start_date, end_date):
    """Itère sur les dates inclusives entre start_date et end_date."""
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _add_event(events_by_date, day, request_item, event_type, recovery_line=None):
    """Ajoute un événement dans le dictionnaire {date: [events]}."""
    events = events_by_date.setdefault(day, [])
    event_label = ""
    if recovery_line is not None:
        event_label = recovery_line.work_description or request_item.project_name or ""
    else:
        event_label = request_item.reason or request_item.project_name or ""
    events.append(
        {
            "date": day,
            "request_id": request_item.id,
            "type": event_type,
            "status": request_item.status,
            "status_label": request_item.status_label,
            "employee_id": request_item.employee_id,
            "employee_name": request_item.employee.display_name,
            "start_date": request_item.start_date,
            "end_date": request_item.end_date,
            "total_days": request_item.total_days,
            "reason": request_item.reason or "",
            "project_name": request_item.project_name or "",
            "label": event_label,
            "request_type_label": request_item.type_label,
            "approval_stage": request_item.approval_stage,
            "recovery_line_id": recovery_line.id if recovery_line else None,
            "recovery_work_date": recovery_line.work_date if recovery_line else None,
            "recovery_start_time": recovery_line.start_time if recovery_line else None,
            "recovery_end_time": recovery_line.end_time if recovery_line else None,
            "recovery_duration_hours": recovery_line.duration_hours if recovery_line else None,
            "is_holiday": bool(recovery_line and recovery_line.is_holiday),
        }
    )


def get_calendar_events_for_employee(
    employee,
    year,
    include_leave=True,
    include_absence=True,
    include_recovery=True,
    include_hr_events=True,
):
    """
    Retourne un dictionnaire {date: [événements]} pour un employé et une année.

    Lit UNIQUEMENT les StaffRequest, RecoveryLine et HREvent existants.
    Respecte les statuts (seuls submitted et approved sont visibles pour les demandes).
    """
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    events_by_date = {}

    # Congés et absences : plages de dates des StaffRequest
    requests = (
        StaffRequest.objects.select_related("employee", "employee__user")
        .filter(
            employee=employee,
            status__in=[StaffRequest.STATUS_SUBMITTED, StaffRequest.STATUS_APPROVED],
        )
        .prefetch_related("recovery_lines")
    )

    for request_item in requests:
        request_type = request_item.request_type
        if request_type == StaffRequest.TYPE_LEAVE and not include_leave:
            continue
        if request_type == StaffRequest.TYPE_ABSENCE and not include_absence:
            continue
        if request_type == StaffRequest.TYPE_RECOVERY:
            continue  # traité via les RecoveryLine

        if not request_item.start_date:
            continue
        end_date = request_item.end_date or request_item.start_date
        range_start = max(request_item.start_date, year_start)
        range_end = min(end_date, year_end)
        if range_start > range_end:
            continue
        for day in _iter_date_range(range_start, range_end):
            _add_event(events_by_date, day, request_item, request_type)

    # Récupérations : lignes de travail par date
    if include_recovery:
        recovery_lines = (
            RecoveryLine.objects.select_related(
                "request", "request__employee", "request__employee__user"
            )
            .filter(
                request__employee=employee,
                request__status__in=[
                    StaffRequest.STATUS_SUBMITTED,
                    StaffRequest.STATUS_APPROVED,
                ],
                work_date__range=(year_start, year_end),
            )
            .order_by("work_date", "start_time")
        )
        for line in recovery_lines:
            _add_event(
                events_by_date,
                line.work_date,
                line.request,
                StaffRequest.TYPE_RECOVERY,
                recovery_line=line,
            )

    # Événements RH : familiaux, repos médical, absences maladie
    if include_hr_events:
        hr_events = (
            HREvent.objects.filter(
                employee=employee,
                status=HREvent.STATUS_ACTIVE,
            )
            .exclude(start_date__isnull=True)
        )
        for event in hr_events:
            end_date = event.end_date or event.start_date
            range_start = max(event.start_date, year_start)
            range_end = min(end_date, year_end)
            if range_start > range_end:
                continue
            for day in _iter_date_range(range_start, range_end):
                events = events_by_date.setdefault(day, [])
                events.append({
                    "date": day,
                    "hr_event_id": event.id,
                    "type": event.event_type,
                    "status": event.status,
                    "status_label": event.status_label,
                    "employee_id": event.employee_id,
                    "employee_name": event.employee.display_name,
                    "start_date": event.start_date,
                    "end_date": event.end_date,
                    "total_days": event.days,
                    "reason": event.reason or "",
                    "project_name": "",
                    "label": event.get_event_type_display(),
                    "request_type_label": event.get_event_type_display(),
                    "is_holiday": False,
                    "recovery_line_id": None,
                    "recovery_work_date": None,
                    "recovery_start_time": None,
                    "recovery_end_time": None,
                    "recovery_duration_hours": None,
                })

    return events_by_date


def get_calendar_holiday_dates(employee, year):
    """
    Retourne l'ensemble des dates fériées connues par l'application
    pour un employé et une année (RecoveryLine.is_holiday=True).
    """
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    holiday_dates = set(
        RecoveryLine.objects.filter(
            request__employee=employee,
            request__status__in=[
                StaffRequest.STATUS_SUBMITTED,
                StaffRequest.STATUS_APPROVED,
            ],
            is_holiday=True,
            work_date__range=(year_start, year_end),
        ).values_list("work_date", flat=True)
    )
    return holiday_dates


def serialize_event(event):
    """Sérialise un événement pour l'API JSON."""
    def fmt_date(value):
        if value is None:
            return ""
        return value.strftime("%d/%m/%Y")

    def fmt_time(value):
        if value is None:
            return ""
        return value.strftime("%H:%M")

    def fmt_decimal(value):
        if value is None:
            return ""
        formatted = format(value, "f").rstrip("0").rstrip(".")
        return formatted or "0"

    return {
        "request_id": event.get("request_id"),
        "hr_event_id": event.get("hr_event_id"),
        "type": event["type"],
        "status": event["status"],
        "status_label": event["status_label"],
        "employee_id": event["employee_id"],
        "employee_name": event["employee_name"],
        "start_date": fmt_date(event.get("start_date")),
        "end_date": fmt_date(event.get("end_date")),
        "total_days": fmt_decimal(event.get("total_days")),
        "reason": event.get("reason", ""),
        "project_name": event.get("project_name", ""),
        "label": event.get("label", ""),
        "request_type_label": event.get("request_type_label", ""),
        "approval_stage": event.get("approval_stage"),
        "recovery_line_id": event.get("recovery_line_id"),
        "recovery_work_date": fmt_date(event.get("recovery_work_date")),
        "recovery_start_time": fmt_time(event.get("recovery_start_time")),
        "recovery_end_time": fmt_time(event.get("recovery_end_time")),
        "recovery_duration_hours": fmt_decimal(event.get("recovery_duration_hours")),
        "is_holiday": bool(event.get("is_holiday")),
        "date": fmt_date(event.get("date")),
    }