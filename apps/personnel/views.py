import json

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from apps.accounts.utils import get_user_profile, normalize_portal_role
from apps.administration.models import LoginBranding
from apps.personnel.models import Role
from apps.requests_management.models import StaffRequest


def _employee_request_queryset(profile):
    return profile.requests.prefetch_related("recovery_lines").order_by("-created_at")


def _get_branding_email():
    branding = LoginBranding.objects.first()
    if not branding:
        return ""
    return (branding.email or "").strip()


def _employee_dashboard_payload(profile):
    request_queryset = _employee_request_queryset(profile)
    stats_by_type = {
        item["request_type"]: item["total"]
        for item in request_queryset.values("request_type").annotate(total=Count("id"))
    }
    stats_by_status = {
        item["status"]: item["total"]
        for item in request_queryset.values("status").annotate(total=Count("id"))
    }
    return {
        "request_queryset": request_queryset,
        "recent_requests": request_queryset[:12],
        "absence_requests": request_queryset.filter(request_type=StaffRequest.TYPE_ABSENCE),
        "recovery_requests": request_queryset.filter(request_type=StaffRequest.TYPE_RECOVERY),
        "leave_requests": request_queryset.filter(request_type=StaffRequest.TYPE_LEAVE),
        "submitted_count": stats_by_status.get(StaffRequest.STATUS_SUBMITTED, 0),
        "approved_count": stats_by_status.get(StaffRequest.STATUS_APPROVED, 0),
        "rejected_count": stats_by_status.get(StaffRequest.STATUS_REJECTED, 0),
        "chart_labels": ["Conge", "Absence", "Recuperation"],
        "chart_values": [
            stats_by_type.get(StaffRequest.TYPE_LEAVE, 0),
            stats_by_type.get(StaffRequest.TYPE_ABSENCE, 0),
            stats_by_type.get(StaffRequest.TYPE_RECOVERY, 0),
        ],
    }


@login_required
def dashboard_view(request):
    profile = get_user_profile(request.user)
    portal_role = normalize_portal_role(request.session.get("portal_role") or profile.role_portal)
    if portal_role != Role.PORTAL_EMPLOYEE and profile.role_portal != Role.PORTAL_EMPLOYEE:
        return redirect("administration:dashboard")

    payload = _employee_dashboard_payload(profile)

    context = {
        "profile": profile,
        "recent_requests": payload["recent_requests"],
        "absence_requests": payload["absence_requests"],
        "recovery_requests": payload["recovery_requests"],
        "leave_requests": payload["leave_requests"],
        "branding_email": _get_branding_email(),
        "submitted_count": payload["submitted_count"],
        "approved_count": payload["approved_count"],
        "rejected_count": payload["rejected_count"],
        "chart_labels": json.dumps(payload["chart_labels"]),
        "chart_values": json.dumps(payload["chart_values"]),
    }
    return render(request, "personnel/dashboard.html", context)


@login_required
def dashboard_data_view(request):
    profile = get_user_profile(request.user)
    portal_role = normalize_portal_role(request.session.get("portal_role") or profile.role_portal)
    if portal_role != Role.PORTAL_EMPLOYEE and profile.role_portal != Role.PORTAL_EMPLOYEE:
        return JsonResponse({"redirect": "administration"})

    payload = _employee_dashboard_payload(profile)

    def format_decimal(value):
        formatted = format(value, "f").rstrip("0").rstrip(".")
        return formatted or "0"

    template_context = {
        "recent_requests": payload["recent_requests"],
        "absence_requests": payload["absence_requests"],
        "recovery_requests": payload["recovery_requests"],
        "leave_requests": payload["leave_requests"],
        "branding_email": _get_branding_email(),
    }
    return JsonResponse(
        {
            "leave_balance": f"{format_decimal(profile.leave_balance)} jours",
            "recovery_balance": f"{format_decimal(profile.recovery_balance)} jours",
            "recent_count": len(payload["recent_requests"]),
            "submitted_count": payload["submitted_count"],
            "approved_count": payload["approved_count"],
            "rejected_count": payload["rejected_count"],
            "chart_labels": payload["chart_labels"],
            "chart_values": payload["chart_values"],
            "recent_requests_html": render_to_string(
                "personnel/includes/recent_requests_rows.html",
                template_context,
                request=request,
            ),
            "absence_requests_html": render_to_string(
                "personnel/includes/request_cards_items.html",
                {
                    **template_context,
                    "items": payload["absence_requests"],
                    "empty_message": "Aucune absence enregistree.",
                    "request_label": "Absence",
                    "delete_title": "Supprimer cette absence",
                    "delete_message": "Cette demande sera retiree de votre historique.",
                },
                request=request,
            ),
            "recovery_requests_html": render_to_string(
                "personnel/includes/request_cards_items.html",
                {
                    **template_context,
                    "items": payload["recovery_requests"],
                    "empty_message": "Aucune recuperation enregistree.",
                    "request_label": "Recuperation",
                    "delete_title": "Supprimer cette recuperation",
                    "delete_message": "Cette demande sera retiree de votre historique.",
                },
                request=request,
            ),
            "leave_requests_html": render_to_string(
                "personnel/includes/request_cards_items.html",
                {
                    **template_context,
                    "items": payload["leave_requests"],
                    "empty_message": "Aucun conge enregistre.",
                    "request_label": "Conge",
                    "delete_title": "Supprimer ce conge",
                    "delete_message": "Cette demande sera retiree de votre historique.",
                },
                request=request,
            ),
        }
    )
