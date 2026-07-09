import json

from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.utils import (
    get_role_code,
    get_user_profile,
    normalize_portal_role,
)
from apps.administration.models import LoginBranding
from apps.administration.views import (
    _build_admin_dashboard_payload,
    _build_requests_overview_context,
)
from apps.mobile_api.models import MobileSessionToken
from apps.personnel.models import EmployeeProfile, Role
from apps.personnel.views import _employee_dashboard_payload
from apps.requests_management.models import StaffRequest


def _json_error(message, status=400):
    return JsonResponse({"ok": False, "message": message}, status=status)


def _parse_json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def _format_decimal(value):
    if value is None:
        return 0
    return float(value)


def _absolute_media_url(request, file_field):
    if not file_field:
        return ""
    try:
        return request.build_absolute_uri(file_field.url)
    except ValueError:
        return ""


def _serialize_branding(request):
    branding = LoginBranding.objects.first()
    if not branding:
        return {
            "site_name": "Centre ValBio",
            "subtitle": "Gestion du personnel",
            "address": "",
            "email": "",
            "website": "",
            "announcement": "",
            "logo_url": "",
            "hero_url": "",
        }
    return {
        "site_name": branding.site_name,
        "subtitle": branding.subtitle,
        "address": branding.address,
        "email": branding.email,
        "website": branding.website,
        "announcement": branding.announcement,
        "logo_url": _absolute_media_url(request, branding.logo_image),
        "hero_url": _absolute_media_url(request, branding.hero_image),
    }


def _serialize_profile(request, profile):
    if not profile:
        return {}
    return {
        "id": profile.id,
        "username": profile.user.username,
        "email": profile.user.email,
        "first_name": profile.user.first_name,
        "last_name": profile.user.last_name,
        "display_name": profile.display_name,
        "position": profile.position,
        "department": profile.department_name,
        "employee_number": profile.employee_number,
        "role_code": profile.role_code,
        "role_label": profile.dashboard_role_label,
        "role_portal": profile.role_portal,
        "leave_balance": _format_decimal(profile.leave_balance),
        "recovery_balance": _format_decimal(profile.recovery_balance),
        "photo_url": _absolute_media_url(request, profile.photo),
        "permissions": {
            "can_manage_settings": profile.can_manage_settings,
            "can_validate_hierarchy": profile.can_validate_hierarchy,
            "can_validate_administration": profile.can_validate_administration,
            "can_validate_direction": profile.can_validate_direction,
        },
    }


def _serialize_request(item):
    return {
        "id": item.id,
        "request_type": item.request_type,
        "request_type_label": item.type_label,
        "status": item.status,
        "status_label": item.status_label,
        "employee_status_label": item.employee_status_label,
        "simple_status_label": item.employee_simple_status_label,
        "approval_stage": item.approval_stage,
        "approval_stage_label": item.get_approval_stage_display(),
        "total_days": _format_decimal(item.total_days),
        "remaining_days_for_reason": _format_decimal(item.remaining_days_for_reason),
        "reason": item.reason,
        "project_name": item.project_name,
        "admin_comment": item.admin_comment,
        "period_label": item.period_label,
        "created_at": item.created_at.isoformat() if item.created_at else "",
        "updated_at": item.updated_at.isoformat() if item.updated_at else "",
        "employee": {
            "id": item.employee_id,
            "display_name": item.employee.display_name,
            "department": item.employee.department_name,
            "position": item.employee.position,
        },
        "stages": {
            "hierarchy": {
                "label": item.hierarchy_status_label,
                "badge": item.hierarchy_status_badge_class,
            },
            "administration": {
                "label": item.administration_status_label,
                "badge": item.administration_status_badge_class,
            },
            "direction": {
                "label": item.direction_status_label,
                "badge": item.direction_status_badge_class,
            },
        },
    }


def _serialize_history_item(item):
    request_item = item["request"]
    stage_statuses = item["stage_statuses"]
    return {
        "request": _serialize_request(request_item),
        "history_stages": {
            "hierarchy": stage_statuses[0],
            "administration": stage_statuses[1],
            "direction": stage_statuses[2],
        },
    }


def _authenticate_mobile_request(request):
    authorization = request.headers.get("Authorization", "").strip()
    if not authorization.startswith("Bearer "):
        return None, None, _json_error("Jeton mobile manquant.", status=401)
    token_key = authorization.split(" ", 1)[1].strip()
    if not token_key:
        return None, None, _json_error("Jeton mobile invalide.", status=401)
    token = (
        MobileSessionToken.objects.select_related("user", "user__profile", "user__profile__role")
        .filter(key=token_key)
        .first()
    )
    if not token:
        return None, None, _json_error("Session mobile introuvable.", status=401)
    profile = get_user_profile(token.user)
    token.last_used_at = timezone.now()
    token.save(update_fields=["last_used_at"])
    return token, profile, None


def _resolve_allowed_roles(selected_role):
    return {
        EmployeeProfile.ROLE_USER: [
            EmployeeProfile.ROLE_USER,
            EmployeeProfile.ROLE_ADMIN,
            EmployeeProfile.ROLE_HIERARCHICAL,
            EmployeeProfile.ROLE_DIRECTION,
        ],
        EmployeeProfile.ROLE_ADMIN: [EmployeeProfile.ROLE_ADMIN],
        EmployeeProfile.ROLE_HIERARCHICAL: [EmployeeProfile.ROLE_HIERARCHICAL],
        EmployeeProfile.ROLE_DIRECTION: [EmployeeProfile.ROLE_DIRECTION],
    }.get(selected_role, [EmployeeProfile.ROLE_USER])


def _build_bootstrap_payload(request, profile):
    return {
        "branding": _serialize_branding(request),
        "profile": _serialize_profile(request, profile),
        "roles": [
            {
                "code": role.code,
                "label_fr": role.label_fr,
                "label_en": role.label_en,
                "label_mg": role.label_mg,
                "portal": role.portal,
            }
            for role in Role.objects.filter(show_in_login=True, is_active=True).order_by("order", "label_fr")
        ],
    }


@csrf_exempt
@require_POST
def login_view(request):
    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("Le corps JSON est invalide.")

    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()
    selected_role = str(payload.get("role", EmployeeProfile.ROLE_USER)).strip() or EmployeeProfile.ROLE_USER

    if not username or not password:
        return _json_error("Le nom d'utilisateur et le mot de passe sont obligatoires.")

    user = authenticate(request, username=username, password=password)
    if not user:
        return _json_error("Identifiants invalides.", status=401)

    profile = get_user_profile(user)
    profile_role_code = get_role_code(profile)
    allowed_roles = _resolve_allowed_roles(selected_role)
    if user.username != "cvbadmin" and profile_role_code not in allowed_roles:
        return _json_error(
            "Le role choisi ne correspond pas aux droits de ce compte.",
            status=403,
        )

    token = MobileSessionToken.objects.create(user=user)
    portal_role = normalize_portal_role(selected_role)

    return JsonResponse(
        {
            "ok": True,
            "token": token.key,
            "portal_role": portal_role,
            "selected_role": selected_role,
            "bootstrap": _build_bootstrap_payload(request, profile),
        }
    )


@csrf_exempt
@require_POST
def logout_view(request):
    token, _profile, error_response = _authenticate_mobile_request(request)
    if error_response:
        return error_response
    token.delete()
    return JsonResponse({"ok": True})


@require_GET
def bootstrap_view(request):
    _token, profile, error_response = _authenticate_mobile_request(request)
    if error_response:
        return error_response
    return JsonResponse({"ok": True, **_build_bootstrap_payload(request, profile)})


@require_GET
def me_view(request):
    _token, profile, error_response = _authenticate_mobile_request(request)
    if error_response:
        return error_response
    return JsonResponse(
        {
            "ok": True,
            "profile": _serialize_profile(request, profile),
            "branding": _serialize_branding(request),
        }
    )


@require_GET
def dashboard_view(request):
    _token, profile, error_response = _authenticate_mobile_request(request)
    if error_response:
        return error_response

    portal_role = normalize_portal_role(request.GET.get("portal") or profile.role_portal)
    if portal_role == Role.PORTAL_EMPLOYEE:
        payload = _employee_dashboard_payload(profile)
        recent_requests = [_serialize_request(item) for item in payload["recent_requests"]]
        return JsonResponse(
            {
                "ok": True,
                "portal": portal_role,
                "summary": {
                    "leave_balance": _format_decimal(profile.leave_balance),
                    "recovery_balance": _format_decimal(profile.recovery_balance),
                    "submitted_count": payload["submitted_count"],
                    "approved_count": payload["approved_count"],
                    "rejected_count": payload["rejected_count"],
                },
                "charts": {
                    "labels": payload["chart_labels"],
                    "values": payload["chart_values"],
                },
                "recent_requests": recent_requests,
            }
        )

    admin_payload = _build_admin_dashboard_payload(profile)
    return JsonResponse(
        {
            "ok": True,
            "portal": portal_role,
            "summary": {
                "employee_count": admin_payload["employee_count"],
                "pending_count": admin_payload["pending_count"],
                "low_leave_count": admin_payload["low_leave_count"],
                "low_recovery_count": admin_payload["low_recovery_count"],
            },
            "charts": {
                "leave_labels": json.loads(admin_payload["leave_chart_labels"]),
                "leave_values": json.loads(admin_payload["leave_chart_values"]),
                "recovery_labels": json.loads(admin_payload["recovery_chart_labels"]),
                "recovery_values": json.loads(admin_payload["recovery_chart_values"]),
            },
        }
    )


@require_GET
def requests_view(request):
    _token, profile, error_response = _authenticate_mobile_request(request)
    if error_response:
        return error_response

    kind = request.GET.get("kind", "").strip().lower()
    portal_role = normalize_portal_role(request.GET.get("portal") or profile.role_portal)

    if portal_role == Role.PORTAL_EMPLOYEE:
        queryset = (
            profile.requests.select_related("employee", "employee__user")
            .prefetch_related("recovery_lines")
            .order_by("-created_at")
        )
        request_type = request.GET.get("type", "").strip().lower()
        if request_type in {
            StaffRequest.TYPE_ABSENCE,
            StaffRequest.TYPE_LEAVE,
            StaffRequest.TYPE_RECOVERY,
        }:
            queryset = queryset.filter(request_type=request_type)
        return JsonResponse(
            {
                "ok": True,
                "portal": portal_role,
                "items": [_serialize_request(item) for item in queryset],
            }
        )

    context = _build_requests_overview_context(profile, show_history=kind == "history")
    if kind == "history":
        return JsonResponse(
            {
                "ok": True,
                "portal": portal_role,
                "items": [_serialize_history_item(item) for item in context["history_requests"]],
            }
        )

    pending_queryset = context["requests"].prefetch_related("recovery_lines").order_by("-created_at")
    return JsonResponse(
        {
            "ok": True,
            "portal": portal_role,
            "pending_count": context["pending_count"],
            "items": [_serialize_request(item) for item in pending_queryset],
        }
    )
