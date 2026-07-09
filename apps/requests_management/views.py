from decimal import Decimal
import base64
import mimetypes
import os
import shutil
import subprocess
import tempfile
import textwrap

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render, resolve_url

from apps.accounts.utils import get_role_code, role_required
from apps.accounts.utils import get_user_profile
from apps.administration.models import LoginBranding
from apps.administration.views import _queue_floating_notification, _send_request_email_alert
from apps.personnel.models import EmployeeProfile
from apps.requests_management.forms import (
    AbsenceRequestForm,
    BaseRecoveryValidationMixin,
    RecoveryLineFormSet,
    RecoveryRequestForm,
)
from apps.requests_management.models import StaffRequest
from django.template.loader import render_to_string


def _request_requires_hierarchy(request_item):
    return request_item.employee.role_code == EmployeeProfile.ROLE_USER


def _get_branding_logo_src(request, branding, export_format=None):
    if not branding or not branding.logo_image:
        return ""

    if export_format:
        try:
            branding.logo_image.open("rb")
            file_bytes = branding.logo_image.read()
            mime_type = mimetypes.guess_type(branding.logo_image.name)[0] or "image/png"
            encoded = base64.b64encode(file_bytes).decode("ascii")
            branding.logo_image.close()
            return f"data:{mime_type};base64,{encoded}"
        except Exception:
            try:
                branding.logo_image.close()
            except Exception:
                pass

    try:
        return request.build_absolute_uri(branding.logo_image.url)
    except Exception:
        return branding.logo_image.url


def _build_print_context(
    request,
    request_item,
    stage_statuses,
    recovery_lines,
    export_format=None,
    back_url=None,
):
    branding = LoginBranding.objects.first()
    return {
        "request_item": request_item,
        "stage_statuses": stage_statuses,
        "recovery_lines": recovery_lines,
        "export_mode": bool(export_format),
        "export_format": export_format,
        "branding": branding,
        "branding_logo_src": _get_branding_logo_src(
            request,
            branding,
            export_format=export_format,
        ),
        "back_url": back_url,
    }


def _get_print_return_url(profile):
    if profile.role_code == EmployeeProfile.ROLE_USER:
        return resolve_url("personnel:dashboard")
    return resolve_url("administration:requests")


def _pdf_escape(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def _build_basic_pdf_bytes(request_item, stage_statuses):
    lines = [
        "Centre ValBio - Demande du personnel",
        f"Type: {request_item.type_label}",
        f"Employe: {request_item.employee.display_name}",
        f"Matricule: {request_item.employee.employee_number or '-'}",
        f"Statut: {request_item.status_label}",
        f"Creee le: {request_item.created_at.strftime('%d/%m/%Y %H:%M')}",
        f"Periode: {request_item.period_label}",
        f"Date debut: {request_item.start_date.strftime('%d/%m/%Y') if request_item.start_date else '-'}",
        f"Date fin: {request_item.end_date.strftime('%d/%m/%Y') if request_item.end_date else '-'}",
        f"Heure debut: {request_item.start_time.strftime('%H:%M') if request_item.start_time else '-'}",
        f"Heure fin: {request_item.end_time.strftime('%H:%M') if request_item.end_time else '-'}",
        f"Total jours: {request_item.total_days}",
        f"Projet: {request_item.project_name or '-'}",
        "Motif:",
    ]

    reason_lines = textwrap.wrap(str(request_item.reason or "-"), width=82) or ["-"]
    lines.extend(reason_lines)
    lines.append("Suivi des validations:")
    for stage in stage_statuses:
        lines.append(
            f"- {stage['label']}: {stage['status']} ({stage['username']})"
        )

    wrapped_lines = []
    for line in lines:
        wrapped_lines.extend(textwrap.wrap(str(line), width=90) or [" "])

    font_size = 11
    line_height = 15
    left_margin = 40
    top_margin = 800

    content_commands = ["BT", f"/F1 {font_size} Tf", f"1 0 0 1 {left_margin} {top_margin} Tm"]
    first_line = True
    for line in wrapped_lines[:45]:
        escaped = _pdf_escape(line)
        if first_line:
            content_commands.append(f"({escaped}) Tj")
            first_line = False
        else:
            content_commands.append(f"0 -{line_height} Td ({escaped}) Tj")
    content_commands.append("ET")
    content_stream = "\n".join(content_commands).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content_stream)).encode("ascii") + b" >>\nstream\n"
        + content_stream
        + b"\nendstream",
    ]

    pdf_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf_bytes))
        pdf_bytes += f"{index} 0 obj\n".encode("ascii")
        pdf_bytes += obj + b"\nendobj\n"

    xref_offset = len(pdf_bytes)
    pdf_bytes += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    pdf_bytes += b"0000000000 65535 f \n"
    for offset in offsets:
        pdf_bytes += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf_bytes += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    ).encode("ascii")
    return pdf_bytes


def _restore_request_balance(request_item):
    if request_item.status != StaffRequest.STATUS_APPROVED:
        return True, ""

    profile = request_item.employee
    amount = request_item.total_days or Decimal("0.0")

    if request_item.request_type == StaffRequest.TYPE_LEAVE:
        profile.leave_balance += amount
        profile.save(update_fields=["leave_balance", "updated_at"])
        return True, "Le solde de conge a ete restaure."

    if request_item.request_type == StaffRequest.TYPE_ABSENCE:
        profile.recovery_balance += amount
        profile.save(update_fields=["recovery_balance", "updated_at"])
        return True, "Le solde de recuperation a ete restaure."

    if request_item.request_type == StaffRequest.TYPE_RECOVERY:
        if profile.recovery_balance < amount:
            return (
                False,
                "Impossible de supprimer cette recuperation approuvee car son solde a deja ete utilise.",
            )
        profile.recovery_balance -= amount
        profile.save(update_fields=["recovery_balance", "updated_at"])
        return True, "Le solde de recuperation a ete ajuste."

    return True, ""


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
        StaffRequest.APPROVAL_ADMINISTRATION: "Ressource Humain (RH)",
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
            "confirm_message": "La demande sera transmise a la Ressource Humain (RH) pour traitement.",
        },
        StaffRequest.TYPE_LEAVE: {
            "page_title": "Demande de conge",
            "heading": "Demande de conge",
            "description": "Formulaire numerique pour demander un conge et suivre automatiquement le solde restant.",
            "submit_label": "Envoyer la demande de conge",
            "confirm_title": "Envoyer cette demande de conge",
            "confirm_message": "La demande de conge sera transmise a la Ressource Humain (RH) pour validation.",
        },
    }
    form = AbsenceRequestForm(
        request.POST or None,
        profile=profile,
        request_type=request_type,
    )
    if profile.role_code == EmployeeProfile.ROLE_USER:
        request_titles[StaffRequest.TYPE_ABSENCE]["confirm_message"] = (
            "La demande sera transmise au chef hierarchique, puis a la Ressource Humain (RH) et a la direction."
        )
        request_titles[StaffRequest.TYPE_LEAVE]["confirm_message"] = (
            "La demande sera transmise au chef hierarchique, puis a la Ressource Humain (RH) et a la direction."
        )
    if request.method == "POST" and form.is_valid():
        balance_request = form.save(commit=False)
        balance_request.employee = profile
        balance_request.request_type = request_type
        balance_request.status = StaffRequest.STATUS_SUBMITTED
        if profile.role_code != EmployeeProfile.ROLE_USER:
            balance_request.approval_stage = StaffRequest.APPROVAL_ADMINISTRATION
        balance_request.save()
        branding = LoginBranding.objects.first()
        _send_request_email_alert(balance_request, branding=branding)
        success_message = (
            "La demande de conge a ete enregistree."
            if request_type == StaffRequest.TYPE_LEAVE
            else "La demande d'absence a ete enregistree."
        )
        _queue_floating_notification(
            request,
            "Demande envoyee",
            success_message,
            action_label="Voir mes demandes",
            action_url=resolve_url("personnel:dashboard"),
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
    if profile.role_code != EmployeeProfile.ROLE_USER:
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
        branding = LoginBranding.objects.first()
        _send_request_email_alert(recovery_request, branding=branding)
        _queue_floating_notification(
            request,
            "Demande envoyee",
            "La fiche de recuperation a ete enregistree.",
            action_label="Voir mes demandes",
            action_url=resolve_url("personnel:dashboard"),
        )
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
    success, balance_message = _restore_request_balance(request_item)
    if not success:
        messages.error(request, balance_message)
        return redirect("personnel:dashboard")
    request_item.delete()
    messages.success(
        request,
        " ".join(
            item
            for item in ["La demande a ete supprimee de votre historique.", balance_message]
            if item
        ),
    )
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
    if request_item.employee_id != profile.id and get_role_code(profile) not in [
        EmployeeProfile.ROLE_ADMIN,
        EmployeeProfile.ROLE_HIERARCHICAL,
        EmployeeProfile.ROLE_DIRECTION,
    ]:
        messages.error(request, "Vous n'avez pas acces a cette demande.")
        return redirect("personnel:dashboard")
    if (
        profile.role_code == EmployeeProfile.ROLE_HIERARCHICAL
        and request_item.employee.department_id != profile.department_id
        and request_item.employee_id != profile.id
    ):
        messages.error(request, "Vous n'avez pas acces a cette demande.")
        return redirect("administration:requests")
    stage_statuses = _build_stage_statuses(request_item)
    recovery_lines = list(request_item.recovery_lines.all())
    back_url = _get_print_return_url(profile)

    download_type = request.GET.get("download")
    if download_type == "png":
        return _build_png_response(request, request_item, stage_statuses, recovery_lines)
    if download_type in ("1", "pdf", "true"):
        return _build_pdf_response(request, request_item, stage_statuses, recovery_lines)

    return render(
        request,
        "requests_management/request_print.html",
        _build_print_context(
            request,
            request_item,
            stage_statuses,
            recovery_lines,
            back_url=back_url,
        ),
    )


def _build_pdf_response(request, request_item, stage_statuses, recovery_lines):
    """Render the printable template to PDF using WeasyPrint when available.

    Falls back to redirect with an error message if WeasyPrint isn't installed.
    """
    context = _build_print_context(
        request,
        request_item,
        stage_statuses,
        recovery_lines,
        export_format="pdf",
    )

    # Attempt WeasyPrint first
    html = render_to_string("requests_management/request_print.html", context, request=request)
    base_url = request.build_absolute_uri("/")

    try:
        from weasyprint import HTML, CSS
        try:
            pdf_bytes = HTML(string=html, base_url=base_url).write_pdf(
                stylesheets=[
                    CSS(
                        string=(
                            "@page { size: A4; margin: 14mm; }"
                            "body { background: #ffffff !important; }"
                            ".print-toolbar { display: none !important; }"
                            ".sheet { width: 182mm !important; min-height: 269mm !important; "
                            "margin: 0 auto !important; padding: 0 !important; box-shadow: none !important; }"
                            ".sheet-content { width: 100% !important; transform: none !important; }"
                        )
                    )
                ]
            )
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            filename = f"demande-{request_item.id}.pdf"
            response["Content-Disposition"] = f"attachment; filename=\"{filename}\""
            return response
        except Exception:
            weasy_error = True
    except Exception:
        weasy_error = True

    # Fallback to wkhtmltopdf binary if available
    wkhtml = shutil.which("wkhtmltopdf")
    if wkhtml:
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".html", encoding="utf-8") as tmp:
                tmp.write(html)
                tmp_path = tmp.name
            cmd = [
                wkhtml,
                "--quiet",
                "--enable-local-file-access",
                "--page-size",
                "A4",
                "--margin-top",
                "14mm",
                "--margin-right",
                "14mm",
                "--margin-bottom",
                "14mm",
                "--margin-left",
                "14mm",
                "--print-media-type",
                tmp_path,
                "-",
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            os.unlink(tmp_path)
            if proc.returncode == 0:
                pdf_bytes = proc.stdout
                response = HttpResponse(pdf_bytes, content_type="application/pdf")
                filename = f"demande-{request_item.id}.pdf"
                response["Content-Disposition"] = f"attachment; filename=\"{filename}\""
                return response
        except Exception:
            pass

    # Final fallback: return a simple but valid PDF instead of a broken file.
    messages.warning(
        request,
        "Le rendu PDF avance n'est pas disponible. Un PDF simplifie a ete genere.",
    )
    pdf_bytes = _build_basic_pdf_bytes(request_item, stage_statuses)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    filename = f"demande-{request_item.id}.pdf"
    response["Content-Disposition"] = f"attachment; filename=\"{filename}\""
    return response


def _build_png_response(request, request_item, stage_statuses, recovery_lines):
    """Render the printable template to PNG.

    Attempts html2image (Chrome/Firefox headless), then WeasyPrint, then wkhtmltoimage, else returns a tiny placeholder PNG.
    """
    context = _build_print_context(
        request,
        request_item,
        stage_statuses,
        recovery_lines,
        export_format="png",
    )
    html = render_to_string("requests_management/request_print.html", context, request=request)
    base_url = request.build_absolute_uri("/")

    # Try html2image (Chrome/Firefox headless - most reliable on Windows)
    try:
        from html2image import Html2Image
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                png_name = f"demande-{request_item.id}.png"
                hti = Html2Image(output_path=tmpdir, size=(794, 1123))
                hti.screenshot(
                    html_str=html,
                    css_str="body { margin: 0; background: #ffffff; }",
                    save_as=png_name,
                    size=(794, 1123),
                )
                png_file = os.path.join(tmpdir, png_name)
                if os.path.exists(png_file):
                    with open(png_file, "rb") as f:
                        png_bytes = f.read()
                    response = HttpResponse(png_bytes, content_type="image/png")
                    filename = f"demande-{request_item.id}.png"
                    response["Content-Disposition"] = f"attachment; filename=\"{filename}\""
                    return response
        except Exception:
            pass
    except Exception:
        pass

    # Try WeasyPrint -> write_png()
    try:
        from weasyprint import HTML
        try:
            png_bytes = HTML(string=html, base_url=base_url).write_png()
            response = HttpResponse(png_bytes, content_type="image/png")
            filename = f"demande-{request_item.id}.png"
            response["Content-Disposition"] = f"attachment; filename=\"{filename}\""
            return response
        except Exception:
            pass
    except Exception:
        pass

    # Try wkhtmltoimage binary
    wkimg = shutil.which("wkhtmltoimage")
    if wkimg:
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".html", encoding="utf-8") as tmp:
                tmp.write(html)
                tmp_html = tmp.name
            tmp_png = tmp_html + ".png"
            cmd = [
                wkimg,
                "--quality",
                "100",
                "--width",
                "794",
                "--height",
                "1123",
                tmp_html,
                tmp_png,
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc.returncode == 0 and os.path.exists(tmp_png):
                with open(tmp_png, "rb") as f:
                    png_bytes = f.read()
                os.unlink(tmp_html)
                os.unlink(tmp_png)
                response = HttpResponse(png_bytes, content_type="image/png")
                filename = f"demande-{request_item.id}.png"
                response["Content-Disposition"] = f"attachment; filename=\"{filename}\""
                return response
        except Exception:
            try:
                os.unlink(tmp_html)
            except Exception:
                pass

    # Fallback: tiny 1x1 transparent PNG
    placeholder_b64 = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
    png_bytes = base64.b64decode(placeholder_b64)
    response = HttpResponse(png_bytes, content_type="image/png")
    filename = f"demande-{request_item.id}.png"
    response["Content-Disposition"] = f"attachment; filename=\"{filename}\""
    messages.warning(request, "Rendu image minimal fourni: installez html2image/wkhtmltoimage pour une vraie capture.")
    return response
