import json

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from apps.accounts.utils import get_user_profile, normalize_portal_role
from apps.administration.models import LoginBranding
from apps.hr_events.hr_events_service import get_hr_events_dashboard_data
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
        "cancelled_count": stats_by_status.get(StaffRequest.STATUS_CANCELLED, 0),
        "chart_labels": ["Conge", "Absence", "Recuperation"],
        "chart_values": [
            stats_by_type.get(StaffRequest.TYPE_LEAVE, 0),
            stats_by_type.get(StaffRequest.TYPE_ABSENCE, 0),
            stats_by_type.get(StaffRequest.TYPE_RECOVERY, 0),
        ],
    }


@login_required
def update_profile_photo_view(request):
    """Permet à l'employé connecté de modifier sa propre photo de profil."""
    from django.contrib import messages as django_messages
    from django.http import JsonResponse
    from django.views.decorators.http import require_POST
    from django.core.files.storage import default_storage
    import os

    profile = get_user_profile(request.user)

    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "Méthode non autorisée."}, status=405)

    # Vérifier que la modification de photo est activée côté backend
    from apps.administration.models import LoginBranding

    branding = LoginBranding.objects.first()
    if branding and not branding.profile_photo_editing_enabled:
        return JsonResponse(
            {"ok": False, "message": "La modification de la photo de profil est désactivée par l'administration."},
            status=403,
        )

    photo_file = request.FILES.get("photo")
    if not photo_file:
        return JsonResponse({"ok": False, "message": "Aucun fichier reçu."}, status=400)

    # Vérifier le format
    allowed_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    ext = os.path.splitext(photo_file.name)[1].lower()
    if ext not in allowed_extensions:
        return JsonResponse(
            {"ok": False, "message": "Format non autorisé. Utilisez JPG, PNG ou WEBP."},
            status=400,
        )

    # Vérifier la taille (5 MB max)
    if photo_file.size > 5 * 1024 * 1024:
        return JsonResponse(
            {"ok": False, "message": "Image trop volumineuse. Taille maximale : 5 MB."},
            status=400,
        )

    # Conserver l'ancienne référence pour suppression après succès
    old_photo = profile.photo
    old_photo_path = None
    if old_photo and old_photo.name:
        old_photo_path = old_photo.name

    # Enregistrer la nouvelle photo
    profile.photo = photo_file
    profile.save(update_fields=["photo", "updated_at"])

    # Supprimer l'ancienne photo physique (si elle existe et n'est pas partagée)
    if old_photo_path and old_photo_path != profile.photo.name:
        try:
            if default_storage.exists(old_photo_path):
                default_storage.delete(old_photo_path)
        except Exception:
            pass

    # Audit log
    try:
        from apps.administration.models import AccountActionHistory

        AccountActionHistory.objects.create(
            actor=request.user,
            target_user=request.user,
            target_username=request.user.username,
            target_display_name=profile.display_name,
            target_role=profile.dashboard_role_label,
            action=AccountActionHistory.ACTION_UPDATED,
            details="Modification de la photo de profil.",
        )
    except Exception:
        pass

    return JsonResponse(
        {
            "ok": True,
            "message": "Photo de profil mise à jour.",
            "photo_url": profile.photo.url if profile.photo else "",
        }
    )


@login_required
def dashboard_view(request):
    profile = get_user_profile(request.user)
    portal_role = normalize_portal_role(request.session.get("portal_role") or profile.role_portal)
    if portal_role != Role.PORTAL_EMPLOYEE and profile.role_portal != Role.PORTAL_EMPLOYEE:
        return redirect("administration:dashboard")

    payload = _employee_dashboard_payload(profile)

    branding = LoginBranding.objects.first()
    profile_photo_editing_enabled = bool(
        branding and branding.profile_photo_editing_enabled
    )

    approved_absences = profile.requests.filter(
        request_type=StaffRequest.TYPE_ABSENCE,
        status=StaffRequest.STATUS_APPROVED,
    ).order_by("-start_date")

    # Total des JOURS d'absence acceptés (somme des total_days, pas le nombre de demandes).
    from decimal import Decimal as Dec

    approved_absence_days = Dec("0.0")
    for absence in approved_absences:
        approved_absence_days += (absence.total_days or Dec("0.0"))

    # Limite d'absence configurée par la RH (absences financées par le solde de récupération).
    from apps.personnel.recovery_service import (
        get_absence_limit,
        get_recovery_limit,
        is_absence_limit_enabled,
        is_recovery_limit_enabled,
    )

    absence_limit_enabled = is_absence_limit_enabled()
    absence_limit = get_absence_limit()

    approved_absence_days_float = float(approved_absence_days)
    absence_limit_float = float(absence_limit)
    remaining_absence_days = max(
        Dec("0.0"), Dec(str(absence_limit_float - approved_absence_days_float))
    )
    percent_used = 0
    if absence_limit_enabled and absence_limit_float > 0:
        percent_used = int(
            round(min(100.0, (approved_absence_days_float / absence_limit_float) * 100.0))
        )

    # Limite de récupération annuelle configurée par la RH.
    recovery_limit_enabled = is_recovery_limit_enabled()
    recovery_limit = get_recovery_limit()
    current_year = timezone.localdate().year
    recovery_balance_current_year = Dec("0.0")
    for item in profile.recovery_window_data:
        if item["year"] == current_year:
            recovery_balance_current_year = item["balance"]
            break
    recovery_balance_current_year_float = float(recovery_balance_current_year)
    recovery_limit_float = float(recovery_limit)
    recovery_remaining = max(
        Dec("0.0"), Dec(str(recovery_limit_float - recovery_balance_current_year_float))
    )
    recovery_percent_used = 0
    if recovery_limit_enabled and recovery_limit_float > 0:
        recovery_percent_used = int(
            round(min(100.0, (recovery_balance_current_year_float / recovery_limit_float) * 100.0))
        )

    def fmt_decimal(value):
        formatted = format(value, "f").rstrip("0").rstrip(".")
        return formatted or "0"

    context = {
        "profile": profile,
        "profile_photo_editing_enabled": profile_photo_editing_enabled,
        "recent_requests": payload["recent_requests"],
        "absence_requests": payload["absence_requests"],
        "recovery_requests": payload["recovery_requests"],
        "leave_requests": payload["leave_requests"],
        "branding_email": _get_branding_email(),
        "submitted_count": payload["submitted_count"],
        "approved_count": payload["approved_count"],
        "rejected_count": payload["rejected_count"],
        "cancelled_count": payload["cancelled_count"],
        "chart_labels": json.dumps(payload["chart_labels"]),
        "chart_values": json.dumps(payload["chart_values"]),
        "leave_window_data": profile.leave_window_data,
        "recovery_window_data": profile.recovery_window_data,
        "approved_absences": approved_absences,
        "approved_absence_days": fmt_decimal(approved_absence_days),
        "absence_limit_enabled": absence_limit_enabled,
        "absence_limit": fmt_decimal(absence_limit),
        "remaining_absence_days": fmt_decimal(remaining_absence_days),
        "absence_percent_used": percent_used,
        "recovery_limit_enabled": recovery_limit_enabled,
        "recovery_limit": fmt_decimal(recovery_limit),
        "recovery_balance_current_year": fmt_decimal(recovery_balance_current_year),
        "recovery_remaining": fmt_decimal(recovery_remaining),
        "recovery_percent_used": recovery_percent_used,
        "hr_events_data": get_hr_events_dashboard_data(profile),
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
            "recovery_balance": f"{format_decimal(profile.recovery_total_balance)} jours",
            "family_event_remaining": format_decimal(profile.family_event_remaining),
            "medical_leave_total": format_decimal(profile.medical_leave_total),
            "sick_absence_total": format_decimal(profile.sick_absence_total),
            "recent_count": len(payload["recent_requests"]),
            "submitted_count": payload["submitted_count"],
            "approved_count": payload["approved_count"],
            "rejected_count": payload["rejected_count"],
            "cancelled_count": payload["cancelled_count"],
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
