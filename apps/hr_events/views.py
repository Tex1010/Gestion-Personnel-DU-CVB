from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.utils import get_user_profile, settings_required
from apps.hr_events.forms import HREventForm
from apps.hr_events.hr_events_service import (
    cancel_hr_event,
    create_hr_event,
    get_hr_events_dashboard_data,
)
from apps.hr_events.models import HREvent
from apps.personnel.models import EmployeeProfile


def _visible_employees(profile):
    """Retourne les employes visibles par le RH."""
    employees = EmployeeProfile.objects.select_related("user").exclude(
        user__username="cvbadmin"
    )
    if profile and profile.can_validate_hierarchy:
        employees = employees.filter(department=profile.department)
    return employees


def _employee_search_values(employee):
    return [
        employee.display_name,
        employee.position or "",
        employee.employee_number or "",
        employee.department_name,
    ]


def _normalize_search_text(value):
    import unicodedata

    normalized_value = unicodedata.normalize("NFD", str(value or "").strip().lower())
    return "".join(
        character for character in normalized_value if unicodedata.category(character) != "Mn"
    )


def _search_matches(search_term, values):
    normalized_term = _normalize_search_text(search_term)
    if not normalized_term:
        return True
    searchable_text = " ".join(
        _normalize_search_text(value) for value in values if value not in (None, "")
    )
    return normalized_term in searchable_text


def _filter_employees_for_search(employees, search_term):
    if not _normalize_search_text(search_term):
        return employees
    return [emp for emp in employees if _search_matches(search_term, _employee_search_values(emp))]


@login_required
@settings_required
def hr_events_list_view(request):
    """Liste tous les evenements RH avec filtres et recherche."""
    profile = get_user_profile(request.user)
    search_term = request.GET.get("search", "")
    event_type_filter = request.GET.get("event_type", "")
    status_filter = request.GET.get("status", "")
    employee_filter = request.GET.get("employee", "")

    events = HREvent.objects.select_related(
        "employee", "employee__user", "created_by"
    ).all()

    if profile and profile.can_validate_hierarchy:
        events = events.filter(employee__department=profile.department)

    if event_type_filter:
        events = events.filter(event_type=event_type_filter)
    if status_filter:
        events = events.filter(status=status_filter)
    if employee_filter:
        events = events.filter(employee_id=employee_filter)

    # Recherche texte
    if search_term and _normalize_search_text(search_term):
        matching_ids = []
        for event in events:
            values = [
                event.employee.display_name,
                event.employee.employee_number or "",
                event.employee.department_name,
                event.get_event_type_display(),
                event.get_status_display(),
                event.reason or "",
                event.start_date.strftime("%d/%m/%Y") if event.start_date else "",
                event.end_date.strftime("%d/%m/%Y") if event.end_date else "",
                str(event.days),
            ]
            if _search_matches(search_term, values):
                matching_ids.append(event.id)
        events = events.filter(id__in=matching_ids)

    events = events.order_by("-created_at")

    # Employes pour le filtre
    employees = _visible_employees(profile)
    employees = _filter_employees_for_search(employees, search_term) if search_term else employees

    context = {
        "events": events,
        "employees": employees,
        "search_term": search_term,
        "event_type_filter": event_type_filter,
        "status_filter": status_filter,
        "employee_filter": employee_filter,
        "event_type_choices": HREvent.TYPE_CHOICES,
        "status_choices": HREvent.STATUS_CHOICES,
    }
    return render(request, "hr_events/hr_events_list.html", context)


@login_required
@settings_required
def hr_event_create_view(request):
    """Cree un nouvel evenement RH."""
    profile = get_user_profile(request.user)
    form = HREventForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        employee = form.cleaned_data["employee"]
        event_type = form.cleaned_data["event_type"]
        days = form.cleaned_data["days"]
        start_date = form.cleaned_data.get("start_date")
        end_date = form.cleaned_data.get("end_date")
        reason = form.cleaned_data.get("reason", "")

        success, result = create_hr_event(
            profile=employee,
            event_type=event_type,
            days=days,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            created_by=request.user,
        )

        if success:
            event = result
            type_label = event.get_event_type_display()
            messages.success(
                request,
                f"L'evenement RH ({type_label}) a ete enregistre pour {employee.display_name}.",
            )
            return redirect("hr_events:list")
        else:
            messages.error(request, result)

    context = {
        "form": form,
        "employees": _visible_employees(profile),
    }
    return render(request, "hr_events/hr_event_form.html", context)


@login_required
@settings_required
def hr_event_cancel_view(request, event_id):
    """Annule un evenement RH."""
    if request.method != "POST":
        return redirect("hr_events:list")

    event = get_object_or_404(HREvent, pk=event_id)
    success, message = cancel_hr_event(event)

    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)

    return redirect("hr_events:list")
