"""
Vues du calendrier RH / Direction / Employé.

Sécurité :
- RH / Direction (approval_required) : peuvent rechercher et consulter les
  employés selon leurs permissions actuelles (_visible_employee_queryset).
- Employé : ne peut consulter QUE son propre calendrier (aucun paramètre
  employee_id accepté). Le back-end applique aussi cette restriction.

Aucun employé n'est sélectionné automatiquement pour RH / Direction :
la sélection est toujours volontaire.
"""

import calendar as cal
import json
import unicodedata
from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.accounts.utils import get_user_profile
from apps.administration.calendar_service import (
    get_calendar_events_for_employee,
    get_calendar_holiday_dates,
    serialize_event,
)
from apps.administration.views import _visible_employee_queryset
from apps.hr_events.models import HREvent
from apps.personnel.models import EmployeeProfile

MONTH_NAMES = [
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
]

# Types d'événements RH spéciaux (HREVENT)
HR_EVENT_TYPES = [
    HREvent.TYPE_FAMILY_EVENT,
    HREvent.TYPE_MEDICAL_LEAVE,
    HREvent.TYPE_SICK_ABSENCE,
]


def _build_year_options(current_year):
    """Retourne les années disponibles autour de l'année courante."""
    return [
        current_year - 2,
        current_year - 1,
        current_year,
        current_year + 1,
        current_year + 2,
    ]


def _resolve_calendar_employee(request, employee_id=None):
    """
    Retourne l'employé à afficher dans le calendrier.

    - RH / Direction : employé volontairement sélectionné (jamais automatique).
      Si aucun employee_id n'est fourni → None (champ vide, aucun calendrier).
    - Employé : uniquement son propre profil.
    """
    profile = get_user_profile(request.user)
    is_staff_viewer = bool(
        profile
        and (
            profile.can_manage_settings
            or profile.can_validate_administration
            or profile.can_validate_direction
            or profile.can_validate_hierarchy
        )
    )

    if not is_staff_viewer:
        # Employé normal : jamais un autre employé.
        return profile

    if not employee_id:
        # Pas de sélection → aucun employé par défaut.
        return None

    employee = get_object_or_404(
        EmployeeProfile.objects.select_related("user", "department"),
        pk=employee_id,
    )
    visible_ids = set(
        _visible_employee_queryset(profile).values_list("id", flat=True)
    )
    if employee.id not in visible_ids:
        return None
    return employee


def _build_calendar_months_from_events(year, employee, events_by_date):
    """
    Construit la grille des 12 mois à partir des événements déjà chargés.
    Évite de re-interroger la base de données.
    """
    calendar_obj = cal.Calendar(firstweekday=0)
    months = []

    if employee is None:
        for name in MONTH_NAMES:
            months.append({"name": name, "weeks": []})
        return months

    holiday_dates = get_calendar_holiday_dates(employee, year)

    for month_index, name in enumerate(MONTH_NAMES):
        month_number = month_index + 1
        weeks = []
        for week in calendar_obj.monthdatescalendar(year, month_number):
            week_days = []
            for day in week:
                if day.month != month_number:
                    week_days.append({"day": None})
                    continue
                date_key = day.isoformat()
                day_events = events_by_date.get(day, [])
                week_days.append(
                    {
                        "day": day.day,
                        "date_key": date_key,
                        "is_weekend": day.weekday() >= 5,
                        "is_holiday": date_key in holiday_dates,
                        "events": [serialize_event(event) for event in day_events],
                    }
                )
            weeks.append(week_days)
        months.append({"name": name, "weeks": weeks})

    return months


def _build_summary_stats(events_by_date):
    """
    Calcule les totaux affichés dans la carte résumé à partir des événements déjà chargés.
    - Congés / Absences : somme des total_days des événements de l'année.
    - Récupérations : somme des recovery_duration_hours.
    - Événements RH : somme des jours pour familiaux, repos médical, absences maladie.
    """
    stats = {
        "leave": 0,
        "absence": 0,
        "recovery": 0,
        "family_event": 0,
        "medical_leave": 0,
        "sick_absence": 0,
    }
    for day_events in events_by_date.values():
        for event in day_events:
            event_type = event.get("type")
            try:
                if event_type == "leave":
                    stats["leave"] += float(event.get("total_days") or 0)
                elif event_type == "absence":
                    stats["absence"] += float(event.get("total_days") or 0)
                elif event_type == "recovery":
                    stats["recovery"] += float(event.get("recovery_duration_hours") or 0)
                elif event_type == HREvent.TYPE_FAMILY_EVENT:
                    stats["family_event"] += float(event.get("total_days") or 0)
                elif event_type == HREvent.TYPE_MEDICAL_LEAVE:
                    stats["medical_leave"] += float(event.get("total_days") or 0)
                elif event_type == HREvent.TYPE_SICK_ABSENCE:
                    stats["sick_absence"] += float(event.get("total_days") or 0)
            except (TypeError, ValueError):
                pass
    return stats


def _format_stat(value, unit):
    formatted = format(value, "f").rstrip("0").rstrip(".")
    return f"{formatted or '0'} {unit}"


def _build_calendar_page_context(request, year, employee, include_leave, include_absence, include_recovery, include_hr_events=True):
    """Construit le contexte partagé de la page calendrier."""
    profile = get_user_profile(request.user)
    is_staff_viewer = bool(
        profile
        and (
            profile.can_manage_settings
            or profile.can_validate_administration
            or profile.can_validate_direction
            or profile.can_validate_hierarchy
        )
    )

    # Employés visibles pour le sélecteur Tom Select (RH / Direction uniquement).
    calendar_employees = []
    if is_staff_viewer:
        visible_employees = _visible_employee_queryset(profile).select_related(
            "user", "department"
        )
        calendar_employees = [
            {
                "id": emp.id,
                "display_name": emp.display_name,
                "username": emp.user.username,
                "employee_number": emp.employee_number or "",
                "position": emp.position or "",
                "department": emp.department.name if emp.department else "",
            }
            for emp in visible_employees
        ]

    # Charger les événements une seule fois pour toutes les utilisations
    events_by_date = {}
    if employee is not None:
        events_by_date = get_calendar_events_for_employee(
            employee,
            year,
            include_leave=include_leave,
            include_absence=include_absence,
            include_recovery=include_recovery,
            include_hr_events=include_hr_events,
        )

    # Grille complète rendue côté serveur (jours toujours visibles).
    months = _build_calendar_months_from_events(year, employee, events_by_date)

    # Statistiques résumées (calculées à partir des événements déjà chargés)
    summary = _build_summary_stats(events_by_date)

    # Événements par date pour les interactions JS (tooltips + modal).
    events_json = "{}"
    if employee is not None:
        serialized_dates = {}
        for day, day_events in events_by_date.items():
            serialized_dates[day.isoformat()] = [
                serialize_event(event) for event in day_events
            ]
        events_json = json.dumps(serialized_dates)

    return {
        "selected_year": year,
        "year_options": _build_year_options(year),
        "current_year": timezone.localdate().year,
        "calendar_employee": employee,
        "is_staff_viewer": is_staff_viewer,
        "can_search_employees": is_staff_viewer,
        "calendar_employees": calendar_employees,
        "months": months,
        "events_json": events_json,
        "summary_leave": _format_stat(summary["leave"], "jour(s)"),
        "summary_absence": _format_stat(summary["absence"], "jour(s)"),
        "summary_recovery": _format_stat(summary["recovery"], "heure(s)"),
        "summary_family_event": _format_stat(summary["family_event"], "jour(s)"),
        "summary_medical_leave": _format_stat(summary["medical_leave"], "jour(s)"),
        "summary_sick_absence": _format_stat(summary["sick_absence"], "jour(s)"),
        "page_title": (
            f"Calendrier du personnel - {employee.display_name}"
            if employee
            else "Calendrier du personnel"
        ),
    }


@login_required
def calendar_view(request):
    """
    Page principale du calendrier.

    RH / Direction : recherche d'employé + sélection d'année.
    Employé : son propre calendrier uniquement.
    """
    profile = get_user_profile(request.user)
    try:
        year = int(request.GET.get("year", timezone.localdate().year))
    except (TypeError, ValueError):
        year = timezone.localdate().year
    year = max(2000, min(year, 2100))

    employee_id = request.GET.get("employee")
    employee = _resolve_calendar_employee(request, employee_id)

    include_leave = request.GET.get("leave", "1") != "0"
    include_absence = request.GET.get("absence", "1") != "0"
    include_recovery = request.GET.get("recovery", "1") != "0"
    include_hr_events = request.GET.get("hr_events", "1") != "0"

    context = _build_calendar_page_context(
        request,
        year,
        employee,
        include_leave,
        include_absence,
        include_recovery,
        include_hr_events=include_hr_events,
    )
    context.update(
        {
            "include_leave": include_leave,
            "include_absence": include_absence,
            "include_recovery": include_recovery,
            "include_hr_events": include_hr_events,
        }
    )

    if request.headers.get("X-Requested-With") == "fetch":
        return JsonResponse(
            {
                "year": year,
                "employee_id": employee.id if employee else None,
                "employee_name": employee.display_name if employee else "",
                "events": json.loads(context["events_json"]),
            }
        )

    return render(request, "administration/calendar.html", context)


@login_required
@require_GET
def calendar_employee_search_view(request):
    """
    Recherche AJAX d'employés pour l'autocomplétion (RH / Direction uniquement).

    Sécurité : un employé normal ne peut pas lister d'autres employés.
    """
    profile = get_user_profile(request.user)
    is_staff_viewer = bool(
        profile
        and (
            profile.can_manage_settings
            or profile.can_validate_administration
            or profile.can_validate_direction
            or profile.can_validate_hierarchy
        )
    )
    if not is_staff_viewer:
        return JsonResponse({"results": []})

    search_term = request.GET.get("term", "").strip()
    employees = _visible_employee_queryset(profile).select_related("user", "department")

    if search_term:
        def normalize(value):
            normalized_value = unicodedata.normalize(
                "NFD", str(value or "").strip().lower()
            )
            return "".join(
                character
                for character in normalized_value
                if unicodedata.category(character) != "Mn"
            )

        normalized_term = normalize(search_term)
        matching = []
        for employee in employees:
            searchable = " ".join(
                normalize(value)
                for value in [
                    employee.display_name,
                    employee.user.username,
                    employee.employee_number or "",
                    employee.position or "",
                    employee.department_name if employee.department else "",
                ]
                if value
            )
            if normalized_term in searchable:
                matching.append(employee)
        employees = matching
    else:
        employees = list(employees[:20])

    results = [
        {
            "id": employee.id,
            "display_name": employee.display_name,
            "username": employee.user.username,
            "employee_number": employee.employee_number or "",
            "position": employee.position or "",
            "department": employee.department_name if employee.department else "",
        }
        for employee in employees
    ]
    return JsonResponse({"results": results})