import io
import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.timezone import localtime

from apps.accounts.utils import role_required
from apps.administration.forms import (
    DepartmentForm,
    EmployeeAccountForm,
    LoginBrandingForm,
    ProjectForm,
)
from apps.administration.models import (
    AccountActionHistory,
    LoginBranding,
    RequestActionHistory,
)
from apps.personnel.models import Department, EmployeeProfile, Project
from apps.requests_management.models import StaffRequest


ADMIN_ROLES = [EmployeeProfile.ROLE_ADMIN]
APPROVAL_ROLES = [EmployeeProfile.ROLE_HIERARCHICAL, EmployeeProfile.ROLE_DIRECTION, *ADMIN_ROLES]


def _format_balance_label(value, unit):
    if value is None:
        return f"0 {unit}"
    formatted = format(value, "f").rstrip("0").rstrip(".")
    return f"{formatted or '0'} {unit}"


def _build_balance_distribution(queryset, field_name, unit):
    distribution = (
        queryset.values(field_name)
        .annotate(total=Count("id"))
        .order_by(field_name)
    )
    labels = [_format_balance_label(item[field_name], unit) for item in distribution]
    values = [item["total"] for item in distribution]
    return json.dumps(labels), json.dumps(values)


def _settings_redirect(panel="create", show_history=False, edit_id=None):
    url = reverse("administration:settings")
    params = [f"panel={panel}"]
    if show_history:
        params.append("show_history=1")
    if edit_id:
        params.append(f"edit={edit_id}")
    return f"{url}?{'&'.join(params)}"


def _requests_redirect(show_history=False):
    url = reverse("administration:requests")
    if show_history:
        return f"{url}?show_history=1"
    return url


def _visible_employee_queryset(profile):
    employees = EmployeeProfile.objects.select_related("user").exclude(
        user__username="cvbadmin"
    )
    if profile and profile.role == EmployeeProfile.ROLE_HIERARCHICAL:
        employees = employees.filter(department=profile.department)
    return employees


def _scoped_request_queryset(queryset, profile, actionable_only=False):
    if not profile:
        return queryset.none()
    if profile.role == EmployeeProfile.ROLE_HIERARCHICAL:
        queryset = queryset.filter(employee__department=profile.department)
        if actionable_only:
            return queryset.filter(
                status=StaffRequest.STATUS_SUBMITTED,
                approval_stage=StaffRequest.APPROVAL_HIERARCHY,
            )
        return queryset
    if profile.role == EmployeeProfile.ROLE_ADMIN:
        if actionable_only:
            return queryset.filter(
                status=StaffRequest.STATUS_SUBMITTED,
                approval_stage=StaffRequest.APPROVAL_ADMINISTRATION,
            )
        return queryset
    if profile.role == EmployeeProfile.ROLE_DIRECTION:
        if actionable_only:
            return queryset.filter(
                status=StaffRequest.STATUS_SUBMITTED,
                approval_stage=StaffRequest.APPROVAL_DIRECTION,
            )
        return queryset
    return queryset.none()


def _export_request_rows(requests):
    headers = [
        "ID",
        "Employe",
        "Matricule",
        "Type",
        "Date de creation",
        "Date debut",
        "Date fin",
        "Periode",
        "Nombre de jours",
        "Statut",
        "Etape",
        "Motif / Projet",
        "Commentaire admin",
    ]
    rows = []
    for item in requests:
        created_label = (
            localtime(item.created_at).strftime("%d/%m/%Y %H:%M")
            if item.created_at
            else ""
        )
        rows.append(
            [
                item.id,
                getattr(item.employee, "display_name", ""),
                getattr(item.employee, "employee_number", ""),
                item.type_label,
                created_label,
                item.start_date.strftime("%d/%m/%Y") if item.start_date else "",
                item.end_date.strftime("%d/%m/%Y") if item.end_date else "",
                item.period_label,
                item.total_days or "",
                item.status_label,
                item.get_approval_stage_display(),
                item.reason or item.project_name or "",
                item.admin_comment or "",
            ]
        )
    return headers, rows


def _build_requests_export_response(request, export_format, requests):
    headers, rows = _export_request_rows(requests)
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Demandes"
    sheet.freeze_panes = "A2"
    sheet.sheet_view.showGridLines = False
    sheet.append(headers)
    for row in rows:
        sheet.append(row)

    header_fill = PatternFill("solid", fgColor="255C3A")
    header_font = Font(color="FFFFFF", bold=True)
    zebra_fill = PatternFill("solid", fgColor="F7FBF8")
    clear_fill = PatternFill("solid", fgColor="FFFFFF")
    border = Border(
        left=Side(style="thin", color="D8E3DB"),
        right=Side(style="thin", color="D8E3DB"),
        top=Side(style="thin", color="D8E3DB"),
        bottom=Side(style="thin", color="D8E3DB"),
    )
    top_alignment = Alignment(vertical="top", wrap_text=True)

    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row):
        row_fill = zebra_fill if row[0].row % 2 == 0 else clear_fill
        for cell in row:
            cell.alignment = top_alignment
            cell.border = border
            cell.fill = row_fill

    width_map = {
        1: 8,
        2: 26,
        3: 16,
        4: 16,
        5: 20,
        6: 18,
        7: 34,
        8: 14,
        9: 16,
        10: 20,
        11: 34,
        12: 30,
    }
    for column_index, width in width_map.items():
        sheet.column_dimensions[get_column_letter(column_index)].width = width

    sheet.row_dimensions[1].height = 28
    for row_index in range(2, sheet.max_row + 1):
        sheet.row_dimensions[row_index].height = 44

    sheet.auto_filter.ref = sheet.dimensions

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=demandes.xlsx"
    return response


def _send_request_email_alert(request_item, branding=None):
    if not branding:
        branding = LoginBranding.objects.first()
    if not branding or not branding.request_submission_email_enabled:
        return False
    recipient = getattr(branding, "email", "").strip()
    if not recipient:
        return False

    subject = "Nouvelle demande de personnel a traiter"
    admin_url = reverse("administration:requests")
    body = (
        f"Une nouvelle demande a ete soumise par {request_item.employee.display_name}.\n"
        f"Type : {request_item.type_label}\n"
        f"Periode : {request_item.start_date or '-'} - {request_item.end_date or '-'}\n"
        f"Nombre de jours : {request_item.total_days}\n"
        f"Motif : {request_item.reason or request_item.project_name or '-'}\n"
        f"Lien : {admin_url}\n"
    )
    try:
        send_mail(subject, body, None, [recipient], fail_silently=True)
        return True
    except Exception:
        return False


def _queue_floating_notification(request, title, message, action_label="", action_url=""):
    request.session["floating_notification"] = {
        "title": title,
        "message": message,
        "action_label": action_label,
        "action_url": action_url,
    }
    request.session.modified = True


def _is_request_in_scope(request_item, profile):
    if not profile:
        return False
    if profile.role == EmployeeProfile.ROLE_HIERARCHICAL:
        return (
            request_item.employee.department_id == profile.department_id
            and request_item.approval_stage == StaffRequest.APPROVAL_HIERARCHY
        )
    if profile.role == EmployeeProfile.ROLE_ADMIN:
        return request_item.approval_stage == StaffRequest.APPROVAL_ADMINISTRATION
    if profile.role == EmployeeProfile.ROLE_DIRECTION:
        return request_item.approval_stage == StaffRequest.APPROVAL_DIRECTION
    return False


def _request_requires_hierarchy(request_item):
    return request_item.employee.role == EmployeeProfile.ROLE_USER


def _build_history_stage_statuses(request_item):
    stage_order = [
        StaffRequest.APPROVAL_HIERARCHY,
        StaffRequest.APPROVAL_ADMINISTRATION,
        StaffRequest.APPROVAL_DIRECTION,
    ]
    signature_map = {
        StaffRequest.APPROVAL_HIERARCHY: request_item.hierarchical_signature,
        StaffRequest.APPROVAL_ADMINISTRATION: request_item.administration_signature,
        StaffRequest.APPROVAL_DIRECTION: request_item.direction_signature,
    }
    label_map = {
        StaffRequest.APPROVAL_HIERARCHY: "Chef hierarchique",
        StaffRequest.APPROVAL_ADMINISTRATION: "Administration",
        StaffRequest.APPROVAL_DIRECTION: "Direction",
    }
    rejection_stage = request_item.approval_stage if request_item.status == StaffRequest.STATUS_REJECTED else ""
    statuses = []

    for stage_key in stage_order:
        required = (
            stage_key != StaffRequest.APPROVAL_HIERARCHY
            or _request_requires_hierarchy(request_item)
        )
        signature = signature_map[stage_key]

        if not required:
            badge_class = "soft"
            status_label = "Non requise"
        elif rejection_stage == stage_key:
            badge_class = StaffRequest.STATUS_REJECTED
            status_label = "Rejetee"
        elif signature:
            badge_class = StaffRequest.STATUS_APPROVED
            status_label = "Approuvee"
        else:
            badge_class = "soft"
            status_label = "Aucune action"

        statuses.append(
            {
                "label": label_map[stage_key],
                "username": signature or "-",
                "status": status_label,
                "badge_class": badge_class,
            }
        )

    return statuses


def _record_account_history(actor, user, action, details=""):
    profile = getattr(user, "profile", None)
    AccountActionHistory.objects.create(
        actor=actor,
        target_user=user,
        target_username=user.username,
        target_display_name=profile.display_name if profile else "",
        target_role=profile.role if profile else "",
        action=action,
        details=details,
    )


def _apply_request_balance(request_item):
    profile = request_item.employee
    amount = request_item.total_days or Decimal("0.0")

    if request_item.request_type == StaffRequest.TYPE_LEAVE:
        if profile.leave_balance < amount:
            return (
                False,
                "Solde de conge insuffisant pour approuver cette demande.",
            )
        profile.leave_balance -= amount
        profile.save(update_fields=["leave_balance", "updated_at"])
        return True, "Le solde de conge a ete mis a jour."

    if request_item.request_type == StaffRequest.TYPE_ABSENCE:
        if profile.recovery_balance < amount:
            return (
                False,
                "Solde de recuperation insuffisant pour approuver cette demande d'absence.",
            )
        profile.recovery_balance -= amount
        profile.save(update_fields=["recovery_balance", "updated_at"])
        return True, "Le solde de recuperation a ete mis a jour."

    if request_item.request_type == StaffRequest.TYPE_RECOVERY:
        profile.recovery_balance += amount
        profile.save(update_fields=["recovery_balance", "updated_at"])
        return True, "Le solde de recuperation a ete augmente."

    return True, "La demande a ete approuvee."


@login_required
@role_required(*APPROVAL_ROLES)
def dashboard_view(request):
    current_profile = getattr(request.user, "profile", None)
    employees = _visible_employee_queryset(current_profile)
    actionable_requests = _scoped_request_queryset(StaffRequest.objects.all(), current_profile, actionable_only=True)
    leave_chart_labels, leave_chart_values = _build_balance_distribution(
        employees,
        "leave_balance",
        "jour(s)",
    )
    recovery_chart_labels, recovery_chart_values = _build_balance_distribution(
        employees,
        "recovery_balance",
        "unite(s)",
    )
    context = {
        "employees": employees,
        "employee_count": employees.count(),
        "pending_count": actionable_requests.count(),
        "low_leave_count": employees.filter(leave_balance__lt=Decimal("2.0")).count(),
        "low_recovery_count": employees.filter(recovery_balance__lt=Decimal("2.0")).count(),
        "leave_chart_labels": leave_chart_labels,
        "leave_chart_values": leave_chart_values,
        "recovery_chart_labels": recovery_chart_labels,
        "recovery_chart_values": recovery_chart_values,
    }
    return render(request, "administration/dashboard.html", context)


@login_required
@role_required(*APPROVAL_ROLES)
def dashboard_data_view(request):
    current_profile = getattr(request.user, "profile", None)
    employees = _visible_employee_queryset(current_profile)
    actionable_requests = _scoped_request_queryset(StaffRequest.objects.all(), current_profile, actionable_only=True)
    leave_chart_labels, leave_chart_values = _build_balance_distribution(
        employees,
        "leave_balance",
        "jour(s)",
    )
    recovery_chart_labels, recovery_chart_values = _build_balance_distribution(
        employees,
        "recovery_balance",
        "unite(s)",
    )
    return JsonResponse(
        {
            "employee_count": employees.count(),
            "pending_count": actionable_requests.count(),
            "low_leave_count": employees.filter(leave_balance__lt=Decimal("2.0")).count(),
            "low_recovery_count": employees.filter(recovery_balance__lt=Decimal("2.0")).count(),
            "leave_chart_labels": json.loads(leave_chart_labels),
            "leave_chart_values": json.loads(leave_chart_values),
            "recovery_chart_labels": json.loads(recovery_chart_labels),
            "recovery_chart_values": json.loads(recovery_chart_values),
        }
    )


@login_required
@role_required(*APPROVAL_ROLES)
def requests_overview_view(request):
    current_profile = getattr(request.user, "profile", None)
    requests = StaffRequest.objects.select_related("employee", "employee__user")
    submitted_requests = _scoped_request_queryset(requests, current_profile, actionable_only=True)
    history_requests = (
        StaffRequest.objects.select_related("employee", "employee__user")
        .filter(admin_history__isnull=False)
        .distinct()
        .order_by("-updated_at", "-created_at")
    )
    if current_profile and current_profile.role == EmployeeProfile.ROLE_HIERARCHICAL:
        history_requests = history_requests.filter(employee__department=current_profile.department)
    history_requests = [
        {
            "request": history_request,
            "stage_statuses": _build_history_stage_statuses(history_request),
        }
        for history_request in history_requests
    ]
    return render(
        request,
        "administration/requests_overview.html",
        {
            "requests": submitted_requests,
            "history_requests": history_requests,
            "pending_count": submitted_requests.count(),
            "show_history": request.GET.get("show_history") == "1",
        },
    )


@login_required
@role_required(*APPROVAL_ROLES)
def export_requests_view(request, export_format):
    current_profile = getattr(request.user, "profile", None)
    requests = StaffRequest.objects.select_related("employee", "employee__user")
    requests = _scoped_request_queryset(requests, current_profile, actionable_only=False)
    requests = requests.order_by("-created_at")
    return _build_requests_export_response(request, "excel", requests)


@login_required
@role_required(*APPROVAL_ROLES)
def request_notifications_state_view(request):
    current_profile = getattr(request.user, "profile", None)
    actionable_requests = _scoped_request_queryset(
        StaffRequest.objects.select_related("employee", "employee__user"),
        current_profile,
        actionable_only=True,
    ).order_by("-updated_at", "-created_at")
    pending_count = actionable_requests.count()
    latest_request = actionable_requests.first()
    latest_event_key = ""
    latest_request_payload = None

    if latest_request and latest_request.updated_at:
        latest_event_key = (
            f"{latest_request.id}:{int(localtime(latest_request.updated_at).timestamp())}"
        )
        latest_request_payload = {
            "id": latest_request.id,
            "employee_name": latest_request.employee.display_name,
            "type_label": latest_request.type_label,
            "period_label": latest_request.period_label,
            "updated_at": localtime(latest_request.updated_at).strftime("%d/%m/%Y %H:%M"),
        }

    return JsonResponse(
        {
            "pending_count": pending_count,
            "latest_event_key": latest_event_key,
            "latest_request": latest_request_payload,
        }
    )


@login_required
def acknowledge_request_notification_view(request):
    return JsonResponse({"ok": True})


@login_required
@role_required(*APPROVAL_ROLES)
@transaction.atomic
def request_action_view(request, request_id, action):
    if request.method != "POST":
        return redirect("administration:requests")

    request_item = get_object_or_404(
        StaffRequest.objects.select_related("employee", "employee__user"),
        pk=request_id,
    )
    if request_item.status != StaffRequest.STATUS_SUBMITTED:
        messages.error(request, "Cette demande a deja ete traitee.")
        return redirect(_requests_redirect(show_history=True))

    comment = request.POST.get("admin_comment", "").strip()
    previous_status = request_item.status
    balance_message = ""

    current_profile = getattr(request.user, "profile", None)
    is_hierarchical = current_profile and current_profile.role == EmployeeProfile.ROLE_HIERARCHICAL
    is_direction = current_profile and current_profile.role == EmployeeProfile.ROLE_DIRECTION
    is_admin = current_profile and current_profile.role in ADMIN_ROLES
    if not _is_request_in_scope(request_item, current_profile):
        messages.error(request, "Cette demande n'est pas disponible dans votre perimetre de validation.")
        return redirect(_requests_redirect(show_history=True))

    if action == "reject":
        if not (is_hierarchical or is_admin or is_direction):
            messages.error(request, "Impossible : seuls les validateurs autorises peuvent traiter cette demande.")
            return redirect(_requests_redirect(show_history=True))
        request_item.status = StaffRequest.STATUS_REJECTED
        history_action = RequestActionHistory.ACTION_REJECTED
        confirmation_message = "La demande a ete rejetee."
        if is_hierarchical:
            request_item.hierarchical_signature = request.user.get_username()
        elif is_admin:
            request_item.administration_signature = request.user.get_username()
        elif is_direction:
            request_item.direction_signature = request.user.get_username()
    elif action == "approve":
        if not (is_hierarchical or is_admin or is_direction):
            messages.error(request, "Impossible : seuls les validateurs autorises peuvent traiter cette demande.")
            return redirect("administration:requests")

        if is_hierarchical:
            if request_item.approval_stage != StaffRequest.APPROVAL_HIERARCHY:
                messages.error(
                    request,
                    "Impossible : cette demande n'est pas encore disponible pour le chef hierarchique.",
                )
                return redirect(_requests_redirect(show_history=True))
            request_item.approval_stage = StaffRequest.APPROVAL_ADMINISTRATION
            request_item.hierarchical_signature = request.user.get_username()
            confirmation_message = "La demande a ete transmise a l'administration."
            history_action = RequestActionHistory.ACTION_APPROVED
        elif is_admin:
            if request_item.approval_stage == StaffRequest.APPROVAL_HIERARCHY:
                messages.error(
                    request,
                    "Impossible : le chef hierarchique doit d'abord valider cette demande.",
                )
                return redirect(_requests_redirect(show_history=True))
            if request_item.approval_stage == StaffRequest.APPROVAL_DIRECTION:
                messages.error(
                    request,
                    "Impossible : la demande a deja ete transmise a la direction.",
                )
                return redirect(_requests_redirect(show_history=True))
            if request_item.approval_stage != StaffRequest.APPROVAL_ADMINISTRATION:
                messages.error(
                    request,
                    "Impossible : cette demande ne correspond pas a votre etape de validation.",
                )
                return redirect(_requests_redirect(show_history=True))
            request_item.approval_stage = StaffRequest.APPROVAL_DIRECTION
            request_item.administration_signature = request.user.get_username()
            confirmation_message = "La demande a ete transmise a la direction."
            history_action = RequestActionHistory.ACTION_APPROVED
        elif is_direction:
            if request_item.approval_stage == StaffRequest.APPROVAL_HIERARCHY:
                messages.error(
                    request,
                    "Impossible : le chef hierarchique doit d'abord valider cette demande.",
                )
                return redirect(_requests_redirect(show_history=True))
            if request_item.approval_stage == StaffRequest.APPROVAL_ADMINISTRATION:
                messages.error(
                    request,
                    "Impossible : l'administration doit d'abord valider cette demande.",
                )
                return redirect(_requests_redirect(show_history=True))
            if request_item.approval_stage != StaffRequest.APPROVAL_DIRECTION:
                messages.error(
                    request,
                    "Impossible : cette demande n'est pas a l'etape de validation de la direction.",
                )
                return redirect(_requests_redirect(show_history=True))
            success, balance_message = _apply_request_balance(request_item)
            if not success:
                messages.error(request, balance_message)
                return redirect("administration:requests")
            request_item.status = StaffRequest.STATUS_APPROVED
            request_item.approval_stage = StaffRequest.APPROVAL_COMPLETED
            request_item.direction_signature = request.user.get_username()
            confirmation_message = "La demande a ete approuvee et finalisee."
            history_action = RequestActionHistory.ACTION_APPROVED
        else:
            messages.error(request, "Impossible : action invalide.")
            return redirect(_requests_redirect(show_history=True))
    else:
        messages.error(request, "Action invalide.")
        return redirect("administration:requests")

    request_item.admin_comment = comment
    request_item.save(update_fields=[
        "status",
        "approval_stage",
        "admin_comment",
        "hierarchical_signature",
        "administration_signature",
        "direction_signature",
        "updated_at",
    ])

    RequestActionHistory.objects.create(
        request=request_item,
        actor=request.user,
        action=history_action,
        previous_status=previous_status,
        new_status=request_item.status,
        comment=comment,
    )

    messages.success(
        request,
        " ".join(
            item
            for item in [confirmation_message, balance_message]
            if item
        ),
    )
    return redirect(_requests_redirect(show_history=True))


@login_required
@role_required(*ADMIN_ROLES)
def request_history_delete_view(request, request_id):
    if request.method != "POST":
        return redirect(_requests_redirect(show_history=True))
    request_item = get_object_or_404(StaffRequest, pk=request_id)
    deleted_count, _ = RequestActionHistory.objects.filter(request=request_item).delete()
    if deleted_count:
        messages.success(request, "L'historique de la demande a ete supprime.")
    else:
        messages.info(request, "Aucune entree d'historique a supprimer pour cette demande.")
    return redirect(_requests_redirect(show_history=True))


@login_required
@role_required(*ADMIN_ROLES)
def account_history_delete_view(request, entry_id):
    if request.method != "POST":
        return redirect(_settings_redirect(panel="accounts", show_history=True))
    if request.user.username != "cvbadmin":
        messages.error(request, "Vous n'avez pas l'autorisation de supprimer cet historique.")
        return redirect(_settings_redirect(panel="accounts", show_history=True))
    entry = get_object_or_404(AccountActionHistory, pk=entry_id)
    entry.delete()
    messages.success(request, "L'entree d'historique a ete supprimee.")
    return redirect(_settings_redirect(panel="accounts", show_history=True))


@login_required
@role_required(*ADMIN_ROLES)
def settings_view(request):
    branding = LoginBranding.objects.first() or LoginBranding.objects.create()
    panel = request.GET.get("panel", "create")
    show_history = request.GET.get("show_history") == "1"
    all_employees = EmployeeProfile.objects.select_related("user", "department")
    employees = all_employees.exclude(user__username="cvbadmin")
    departments = Department.objects.filter(is_active=True).order_by("name")
    projects = Project.objects.order_by("name")

    edit_profile = None
    if request.GET.get("edit"):
        edit_profile = get_object_or_404(all_employees, pk=request.GET["edit"])
        if edit_profile.user.username == "cvbadmin" or edit_profile.user.is_superuser:
            messages.error(request, "Ce compte est protege et ne peut pas etre modifie ici.")
            return redirect(_settings_redirect(panel="accounts", show_history=show_history))
        panel = "accounts"

    department_form = DepartmentForm()
    project_form = ProjectForm()
    account_form = EmployeeAccountForm()
    edit_account_form = EmployeeAccountForm(profile=edit_profile) if edit_profile else None
    branding_form = LoginBrandingForm(instance=branding)

    if request.method == "POST":
        panel = request.POST.get("panel", panel)
        show_history = request.POST.get("show_history") == "1"

        if "create-account" in request.POST:
            account_form = EmployeeAccountForm(request.POST, request.FILES)
            if account_form.is_valid():
                user = account_form.save()
                _record_account_history(
                    request.user,
                    user,
                    AccountActionHistory.ACTION_CREATED,
                    "Compte cree depuis les parametres.",
                )
                messages.success(request, "Le compte employe a ete cree.")
                return redirect(_settings_redirect(panel="create"))

        elif "update-account" in request.POST:
            edit_profile = get_object_or_404(all_employees, pk=request.POST.get("profile_id"))
            if edit_profile.user == request.user:
                messages.error(request, "La modification du compte connecte se fait hors de cet ecran.")
                return redirect(_settings_redirect(panel="accounts"))
            if edit_profile.user.username == "cvbadmin" or edit_profile.user.is_superuser:
                messages.error(request, "Ce compte est protege et ne peut pas etre modifie ici.")
                return redirect(_settings_redirect(panel="accounts", show_history=True))
            edit_account_form = EmployeeAccountForm(
                request.POST,
                request.FILES,
                profile=edit_profile,
            )
            if edit_account_form.is_valid():
                user = edit_account_form.save()
                _record_account_history(
                    request.user,
                    user,
                    AccountActionHistory.ACTION_UPDATED,
                    "Compte modifie depuis les parametres.",
                )
                messages.success(request, "Le compte a ete modifie.")
                return redirect(_settings_redirect(panel="accounts", show_history=True))

        elif "delete-account" in request.POST:
            target_profile = get_object_or_404(all_employees, pk=request.POST.get("profile_id"))
            target_user = target_profile.user
            if target_user == request.user:
                messages.error(request, "Vous ne pouvez pas supprimer votre session en cours.")
                return redirect(_settings_redirect(panel="accounts"))
            if target_user.username == "cvbadmin" or target_user.is_superuser:
                messages.error(request, "Ce compte est protege et ne peut pas etre supprime.")
                return redirect(_settings_redirect(panel="accounts", show_history=True))
            _record_account_history(
                request.user,
                target_user,
                AccountActionHistory.ACTION_DELETED,
                "Compte supprime depuis les parametres.",
            )
            target_user.delete()
            messages.success(request, "Le compte a ete supprime.")
            return redirect(_settings_redirect(panel="accounts", show_history=True))

        elif "save-branding" in request.POST:
            branding_form = LoginBrandingForm(
                request.POST,
                request.FILES,
                instance=branding,
            )
            if branding_form.is_valid():
                branding_form.save()
                messages.success(request, "L'identite visuelle et les preferences d'alerte email ont ete mises a jour.")
                return redirect(_settings_redirect(panel="branding"))

        elif "save-department" in request.POST:
            department_form = DepartmentForm(request.POST)
            if department_form.is_valid():
                department_form.save()
                messages.success(request, "Le departement a ete enregistre.")
                return redirect(_settings_redirect(panel="departments"))

        elif "update-department" in request.POST:
            department = get_object_or_404(Department, pk=request.POST.get("department_id"))
            department_form = DepartmentForm(request.POST, instance=department)
            if department_form.is_valid():
                department_form.save()
                messages.success(request, "Le departement a ete mis a jour.")
                return redirect(_settings_redirect(panel="departments"))

        elif "delete-department" in request.POST:
            department = get_object_or_404(Department, pk=request.POST.get("department_id"))
            department.delete()
            messages.success(request, "Le departement a ete supprime.")
            return redirect(_settings_redirect(panel="departments"))

        elif "save-project" in request.POST:
            project_form = ProjectForm(request.POST)
            if project_form.is_valid():
                project_form.save()
                messages.success(request, "Le projet a ete enregistre.")
                return redirect(_settings_redirect(panel="projects"))

        elif "update-project" in request.POST:
            project = get_object_or_404(Project, pk=request.POST.get("project_id"))
            project_form = ProjectForm(request.POST, instance=project)
            if project_form.is_valid():
                project_form.save()
                messages.success(request, "Le projet a ete mis a jour.")
                return redirect(_settings_redirect(panel="projects"))

        elif "delete-project" in request.POST:
            project = get_object_or_404(Project, pk=request.POST.get("project_id"))
            project.delete()
            messages.success(request, "Le projet a ete supprime.")
            return redirect(_settings_redirect(panel="projects"))

        if panel == "create" and not account_form.is_bound:
            account_form = EmployeeAccountForm()
        if panel == "branding" and not branding_form.is_bound:
            branding_form = LoginBrandingForm(instance=branding)

    account_history = AccountActionHistory.objects.select_related("actor")
    department_editor = None
    project_editor = None
    if request.GET.get("edit_department"):
        department_editor = get_object_or_404(Department, pk=request.GET["edit_department"])
        department_form = DepartmentForm(instance=department_editor)
    if request.GET.get("edit_project"):
        project_editor = get_object_or_404(Project, pk=request.GET["edit_project"])
        project_form = ProjectForm(instance=project_editor)

    return render(
        request,
        "administration/settings.html",
        {
            "account_form": account_form,
            "edit_account_form": edit_account_form,
            "branding_form": branding_form,
            "department_form": department_form,
            "project_form": project_form,
            "departments": departments,
            "projects": projects,
            "department_editor": department_editor,
            "project_editor": project_editor,
            "employees": employees,
            "account_history": account_history,
            "panel": panel,
            "show_history": show_history,
            "edit_profile": edit_profile,
        },
    )
