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


def _build_calendar_months(
    year,
    employee,
    include_leave=True,
    include_absence=True,
    include_recovery=True,
):
    """
    Construit la grille complète des 12 mois (rendu côté serveur).

    Chaque mois contient :
    - name : nom du mois.
    - weeks : liste de semaines ; chaque semaine est une liste de 7 cellules.
      Une cellule est soit {"day": None} (jour hors mois), soit :
        day         : numéro du jour
        date_key    : date ISO (YYYY-MM-DD)
        is_weekend  : samedi/dimanche
        is_holiday  : jour férié connu par l'application
        events      : liste d'événements sérialisés pour ce jour
    """
    calendar_obj = cal.Calendar(firstweekday=0)  # Lundi = premier jour
    months = []

    if employee is None:
        for name in MONTH_NAMES:
            months.append({"name": name, "weeks": []})
        return months

    events_by_date = get_calendar_events_for_employee(
        employee,
        year,
        include_leave=include_leave,
        include_absence=include_absence,
        include_recovery=include_recovery,
    )
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


def _build_summary_stats(employee, year):
    """
    Calcule les totaux affichés dans la carte résumé (données existantes uniquement).
    - Congés / Absences : somme des total_days des événements de l'année.
    - Récupérations : somme des recovery_duration_hours.
    """
    stats = {"leave": 0, "absence": 0, "recovery": 0}
    if employee is None:
        return stats

    events_by_date = get_calendar_events_for_employee(
        employee,
        year,
        include_leave=True,
        include_absence=True,
        include_recovery=True,
    )
    for day_events in events_by_date.values():
        for event in day_events:
            if event["type"] == "leave":
                try:
                    stats["leave"] += float(event.get("total_days") or 0)
                except (TypeError, ValueError):
                    pass
            elif event["type"] == "absence":
                try:
                    stats["absence"] += float(event.get("total_days") or 0)
                except (TypeError, ValueError):
                    pass
            elif event["type"] == "recovery":
                try:
                    stats["recovery"] += float(
                        event.get("recovery_duration_hours") or 0
                    )
                except (TypeError, ValueError):
                    pass
    return stats


def _format_stat(value, unit):
    formatted = format(value, "f").rstrip("0").rstrip(".")
    return f"{formatted or '0'} {unit}"


def _build_calendar_page_context(request, year, employee, include_leave, include_absence, include_recovery):
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

    # Grille complète rendue côté serveur (jours toujours visibles).
    months = _build_calendar_months(
        year,
        employee,
        include_leave=include_leave,
        include_absence=include_absence,
        include_recovery=include_recovery,
    )
    summary = _build_summary_stats(employee, year)

    # Événements par date pour les interactions JS (tooltips + modal).
    events_json = "{}"
    if employee is not None:
        events_by_date = get_calendar_events_for_employee(
            employee,
            year,
            include_leave=include_leave,
            include_absence=include_absence,
            include_recovery=include_recovery,
        )
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

    context = _build_calendar_page_context(
        request,
        year,
        employee,
        include_leave,
        include_absence,
        include_recovery,
    )
    context.update(
        {
            "include_leave": include_leave,
            "include_absence": include_absence,
            "include_recovery": include_recovery,
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
        import unicodedata

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