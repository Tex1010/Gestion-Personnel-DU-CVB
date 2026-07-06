import json

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import redirect, render

from apps.accounts.utils import get_user_profile, normalize_portal_role
from apps.personnel.models import Role
from apps.requests_management.models import StaffRequest


@login_required
def dashboard_view(request):
    profile = get_user_profile(request.user)
    portal_role = normalize_portal_role(request.session.get("portal_role") or profile.role_portal)
    if portal_role != Role.PORTAL_EMPLOYEE and profile.role_portal != Role.PORTAL_EMPLOYEE:
        return redirect("administration:dashboard")

    request_queryset = profile.requests.prefetch_related("recovery_lines").order_by("-created_at")
    stats_by_type = {
        item["request_type"]: item["total"]
        for item in request_queryset.values("request_type").annotate(total=Count("id"))
    }
    stats_by_status = {
        item["status"]: item["total"]
        for item in request_queryset.values("status").annotate(total=Count("id"))
    }
    recent_requests = request_queryset[:12]

    context = {
        "profile": profile,
        "recent_requests": recent_requests,
        "absence_requests": request_queryset.filter(request_type=StaffRequest.TYPE_ABSENCE),
        "recovery_requests": request_queryset.filter(request_type=StaffRequest.TYPE_RECOVERY),
        "leave_requests": request_queryset.filter(request_type=StaffRequest.TYPE_LEAVE),
        "submitted_count": stats_by_status.get(StaffRequest.STATUS_SUBMITTED, 0),
        "approved_count": stats_by_status.get(StaffRequest.STATUS_APPROVED, 0),
        "rejected_count": stats_by_status.get(StaffRequest.STATUS_REJECTED, 0),
        "chart_labels": json.dumps(["Conge", "Absence", "Recuperation"]),
        "chart_values": json.dumps(
            [
                stats_by_type.get(StaffRequest.TYPE_LEAVE, 0),
                stats_by_type.get(StaffRequest.TYPE_ABSENCE, 0),
                stats_by_type.get(StaffRequest.TYPE_RECOVERY, 0),
            ]
        ),
    }
    return render(request, "personnel/dashboard.html", context)


@login_required
def dashboard_data_view(request):
    profile = get_user_profile(request.user)
    portal_role = normalize_portal_role(request.session.get("portal_role") or profile.role_portal)
    if portal_role != Role.PORTAL_EMPLOYEE and profile.role_portal != Role.PORTAL_EMPLOYEE:
        return JsonResponse({"redirect": "administration"})

    request_queryset = profile.requests.all().order_by("-created_at")
    stats_by_type = {
        item["request_type"]: item["total"]
        for item in request_queryset.values("request_type").annotate(total=Count("id"))
    }
    stats_by_status = {
        item["status"]: item["total"]
        for item in request_queryset.values("status").annotate(total=Count("id"))
    }

    def format_decimal(value):
        formatted = format(value, "f").rstrip("0").rstrip(".")
        return formatted or "0"

    recent_requests = list(request_queryset[:12])
    return JsonResponse(
        {
            "leave_balance": f"{format_decimal(profile.leave_balance)} jours",
            "recovery_balance": f"{format_decimal(profile.recovery_balance)} jours",
            "recent_count": len(recent_requests),
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
    )
