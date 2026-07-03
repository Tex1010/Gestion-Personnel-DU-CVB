from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.utils import get_user_profile, role_required
from apps.personnel.models import EmployeeProfile
from apps.requests_management.forms import (
    AbsenceRequestForm,
    BaseRecoveryValidationMixin,
    RecoveryLineFormSet,
    RecoveryRequestForm,
)
from apps.requests_management.models import StaffRequest


def _request_requires_hierarchy(request_item):
    return request_item.employee.role == EmployeeProfile.ROLE_USER


def _build_stage_statuses(request_item):
    current_stage = request_item.approval_stage
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
    statuses = []
    for stage_key in stage_order:
        required = stage_key != StaffRequest.APPROVAL_HIERARCHY or _request_requires_hierarchy(request_item)
        signature = signature_map[stage_key]
        if not required:
            stage_status = "Non requise"
        elif request_item.status == StaffRequest.STATUS_APPROVED:
            stage_status = "Approuvee"
        elif request_item.status == StaffRequest.STATUS_REJECTED:
            if current_stage == stage_key:
                stage_status = "Rejetee"
            elif signature:
                stage_status = "Approuvee"
            else:
                stage_status = "Non atteinte"
        elif signature:
            stage_status = "Approuvee"
        elif current_stage == stage_key:
            stage_status = "En attente"
        elif stage_order.index(stage_key) > stage_order.index(current_stage):
            stage_status = "A venir"
        else:
            stage_status = "En attente"
        statuses.append(
            {
                "label": label_map[stage_key],
                "username": signature or "-",
                "status": stage_status,
            }
        )
    return statuses


@login_required
@role_required(
    EmployeeProfile.ROLE_USER,
    EmployeeProfile.ROLE_ADMIN,
    EmployeeProfile.ROLE_HIERARCHICAL,
    EmployeeProfile.ROLE_DIRECTION,
)
def _balance_request_view(request, request_type):
    profile = get_user_profile(request.user)
    request_titles = {
        StaffRequest.TYPE_ABSENCE: {
            "page_title": "Demande d'absence",
            "heading": "Demande d'autorisation d'absence",
            "description": "Formulaire inspire de la fiche papier fournie pour le Centre ValBio.",
            "submit_label": "Envoyer la demande d'absence",
            "confirm_title": "Envoyer cette demande d'absence",
            "confirm_message": "La demande sera transmise a l'administration pour traitement.",
        },
        StaffRequest.TYPE_LEAVE: {
            "page_title": "Demande de conge",
            "heading": "Demande de conge",
            "description": "Formulaire numerique pour demander un conge et suivre automatiquement le solde restant.",
            "submit_label": "Envoyer la demande de conge",
            "confirm_title": "Envoyer cette demande de conge",
            "confirm_message": "La demande de conge sera transmise a l'administration pour validation.",
        },
    }
    form = AbsenceRequestForm(
        request.POST or None,
        profile=profile,
        request_type=request_type,
    )
    if profile.role == EmployeeProfile.ROLE_USER:
        request_titles[StaffRequest.TYPE_ABSENCE]["confirm_message"] = (
            "La demande sera transmise au chef hierarchique, puis a l'administration et a la direction."
        )
        request_titles[StaffRequest.TYPE_LEAVE]["confirm_message"] = (
            "La demande sera transmise au chef hierarchique, puis a l'administration et a la direction."
        )
    if request.method == "POST" and form.is_valid():
        balance_request = form.save(commit=False)
        balance_request.employee = profile
        balance_request.request_type = request_type
        balance_request.status = StaffRequest.STATUS_SUBMITTED
        if profile.role != EmployeeProfile.ROLE_USER:
            balance_request.approval_stage = StaffRequest.APPROVAL_ADMINISTRATION
        balance_request.save()
        success_message = (
            "La demande de conge a ete enregistree."
            if request_type == StaffRequest.TYPE_LEAVE
            else "La demande d'absence a ete enregistree."
        )
        messages.success(request, success_message)
        return redirect("personnel:dashboard")

    return render(
        request,
        "requests_management/absence_form.html",
        {
            "form": form,
            "profile": profile,
            "request_type": request_type,
            **request_titles[request_type],
        },
    )


@login_required
@role_required(
    EmployeeProfile.ROLE_USER,
    EmployeeProfile.ROLE_ADMIN,
    EmployeeProfile.ROLE_HIERARCHICAL,
    EmployeeProfile.ROLE_DIRECTION,
)
def absence_request_view(request):
    return _balance_request_view(request, StaffRequest.TYPE_ABSENCE)


@login_required
@role_required(
    EmployeeProfile.ROLE_USER,
    EmployeeProfile.ROLE_ADMIN,
    EmployeeProfile.ROLE_HIERARCHICAL,
    EmployeeProfile.ROLE_DIRECTION,
)
def leave_request_view(request):
    return _balance_request_view(request, StaffRequest.TYPE_LEAVE)


@login_required
@role_required(
    EmployeeProfile.ROLE_USER,
    EmployeeProfile.ROLE_ADMIN,
    EmployeeProfile.ROLE_HIERARCHICAL,
    EmployeeProfile.ROLE_DIRECTION,
)
def recovery_request_view(request):
    profile = get_user_profile(request.user)
    recovery_request = StaffRequest(
        employee=profile,
        request_type=StaffRequest.TYPE_RECOVERY,
        status=StaffRequest.STATUS_SUBMITTED,
    )
    if profile.role != EmployeeProfile.ROLE_USER:
        recovery_request.approval_stage = StaffRequest.APPROVAL_ADMINISTRATION
    form = RecoveryRequestForm(request.POST or None, instance=recovery_request)
    formset = RecoveryLineFormSet(request.POST or None, instance=recovery_request)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        if not BaseRecoveryValidationMixin.has_any_completed_line(formset):
            messages.error(
                request,
                "Ajoutez au moins une ligne de travail dans la fiche de recuperation.",
            )
            return render(
                request,
                "requests_management/recovery_form.html",
                {"form": form, "formset": formset, "profile": profile},
            )
        recovery_request = form.save(commit=False)
        recovery_request.employee = profile
        recovery_request.request_type = StaffRequest.TYPE_RECOVERY
        recovery_request.status = StaffRequest.STATUS_SUBMITTED
        recovery_request.save()
        formset.instance = recovery_request
        lines = formset.save(commit=False)
        total_hours = Decimal("0.0")
        for line in lines:
            line.request = recovery_request
            line.save()
            total_hours += line.duration_hours
        recovery_request.total_days = total_hours
        recovery_request.save(update_fields=["total_days", "updated_at"])
        messages.success(request, "La fiche de recuperation a ete enregistree.")
        return redirect("personnel:dashboard")

    return render(
        request,
        "requests_management/recovery_form.html",
        {"form": form, "formset": formset, "profile": profile},
    )


@login_required
@role_required(
    EmployeeProfile.ROLE_USER,
    EmployeeProfile.ROLE_ADMIN,
    EmployeeProfile.ROLE_HIERARCHICAL,
    EmployeeProfile.ROLE_DIRECTION,
)
def delete_request_view(request, request_id):
    if request.method != "POST":
        return redirect("personnel:dashboard")

    profile = get_user_profile(request.user)
    request_item = get_object_or_404(
        StaffRequest.objects.select_related("employee", "employee__user"),
        pk=request_id,
        employee=profile,
    )
    if request_item.status != StaffRequest.STATUS_SUBMITTED:
        messages.error(request, "Seules les demandes encore en attente peuvent etre supprimees.")
        return redirect("personnel:dashboard")
    request_item.delete()
    messages.success(request, "La demande a ete supprimee de votre historique.")
    return redirect("personnel:dashboard")


@login_required
@role_required(
    EmployeeProfile.ROLE_USER,
    EmployeeProfile.ROLE_ADMIN,
    EmployeeProfile.ROLE_HIERARCHICAL,
    EmployeeProfile.ROLE_DIRECTION,
)
def print_request_view(request, request_id):
    profile = get_user_profile(request.user)
    request_item = get_object_or_404(
        StaffRequest.objects.select_related("employee", "employee__user", "employee__department").prefetch_related("recovery_lines"),
        pk=request_id,
    )
    if request_item.employee_id != profile.id and profile.role not in [
        EmployeeProfile.ROLE_ADMIN,
        EmployeeProfile.ROLE_HIERARCHICAL,
        EmployeeProfile.ROLE_DIRECTION,
    ]:
        messages.error(request, "Vous n'avez pas acces a cette demande.")
        return redirect("personnel:dashboard")
    if (
        profile.role == EmployeeProfile.ROLE_HIERARCHICAL
        and request_item.employee.department_id != profile.department_id
        and request_item.employee_id != profile.id
    ):
        messages.error(request, "Vous n'avez pas acces a cette demande.")
        return redirect("administration:requests")

    return render(
        request,
        "requests_management/request_print.html",
        {
            "request_item": request_item,
            "stage_statuses": _build_stage_statuses(request_item),
            "recovery_lines": request_item.recovery_lines.all(),
        },
    )
