from datetime import datetime
from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from apps.personnel.models import Project
from apps.requests_management.models import RecoveryLine, StaffRequest


class AbsenceRequestForm(forms.ModelForm):
    def __init__(self, *args, profile=None, request_type=StaffRequest.TYPE_ABSENCE, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile
        self.request_type = request_type
        self.fields["remaining_days_for_reason"].required = False
        self.fields["remaining_days_for_reason"].widget.attrs.update(
            {
                "readonly": "readonly",
                "data-remaining-balance": "1",
            }
        )

        current_balance = Decimal("0.0")
        if self.profile:
            if self.request_type == StaffRequest.TYPE_LEAVE:
                current_balance = self.profile.leave_balance
            else:
                current_balance = self.profile.recovery_balance

        self.fields["total_days"].required = False
        self.fields["total_days"].widget.attrs.update(
            {
                "readonly": "readonly",
                "data-total-days": "1",
            }
        )
        self.fields["remaining_days_for_reason"].widget.attrs["data-current-balance"] = str(
            current_balance
        )
        raw_total_days = self.initial.get("total_days") or self.data.get("total_days") or "0"
        try:
            initial_total_days = Decimal(str(raw_total_days))
        except Exception:
            initial_total_days = Decimal("0.0")
        self.initial["remaining_days_for_reason"] = max(
            Decimal("0.0"), current_balance - initial_total_days
        )

    class Meta:
        model = StaffRequest
        fields = ["start_date", "end_date", "total_days", "reason", "remaining_days_for_reason"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        total_days = cleaned_data.get("total_days")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "La date de fin doit etre apres la date de debut.")
        if start_date and end_date and not total_days:
            cleaned_data["total_days"] = Decimal((end_date - start_date).days + 1)
            total_days = cleaned_data["total_days"]

        current_balance = Decimal("0.0")
        if self.profile:
            if self.request_type == StaffRequest.TYPE_LEAVE:
                current_balance = self.profile.leave_balance
            else:
                current_balance = self.profile.recovery_balance

        if total_days is not None:
            remaining = current_balance - total_days
            if remaining < Decimal("0.0"):
                target_label = (
                    "solde de conge"
                    if self.request_type == StaffRequest.TYPE_LEAVE
                    else "solde de recuperation"
                )
                self.add_error(
                    "total_days",
                    f"Le nombre demande depasse votre {target_label} disponible.",
                )
                remaining = Decimal("0.0")
            cleaned_data["remaining_days_for_reason"] = remaining
        return cleaned_data


class RecoveryRequestForm(forms.ModelForm):
    project_name = forms.ChoiceField(
        label="Projet",
        required=False,
        choices=[("", "Selectionner un projet")],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        project_choices = [("", "Selectionner un projet")]
        project_choices.extend(
            (project.name, project.name)
            for project in Project.objects.filter(is_active=True).order_by("name")
        )
        current_value = self.initial.get("project_name") or self.data.get("project_name") or getattr(self.instance, "project_name", "")
        if current_value and current_value not in {choice[0] for choice in project_choices}:
            project_choices.append((current_value, current_value))
        self.fields["project_name"].choices = project_choices

    class Meta:
        model = StaffRequest
        fields = ["project_name", "reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 2})}


class RecoveryLineForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["duration_hours"].required = False
        self.fields["duration_hours"].widget.attrs.update(
            {
                "readonly": "readonly",
                "inputmode": "decimal",
                "step": "0.1",
                "data-duration-days": "1",
            }
        )
        self.fields["work_date"].widget.attrs["data-work-date"] = "1"
        self.fields["work_description"].widget.attrs["data-work-description"] = "1"
        self.fields["start_time"].widget.attrs["data-start-time"] = "1"
        self.fields["end_time"].widget.attrs["data-end-time"] = "1"
        self.fields["is_holiday"].widget.attrs["data-is-holiday"] = "1"

    class Meta:
        model = RecoveryLine
        fields = ["work_date", "work_description", "start_time", "end_time", "duration_hours", "is_holiday"]
        widgets = {
            "work_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        is_holiday = cleaned_data.get("is_holiday") or False
        if start_time and end_time:
            start_minutes = start_time.hour * 60 + start_time.minute
            end_minutes = end_time.hour * 60 + end_time.minute
            if end_minutes <= start_minutes:
                self.add_error("end_time", "L'heure de fin doit etre apres l'heure de debut.")
                return cleaned_data

            pause_start = 12 * 60
            pause_end = 13 * 60
            overlap = max(0, min(end_minutes, pause_end) - max(start_minutes, pause_start))
            worked_minutes = (end_minutes - start_minutes) - overlap
            worked_hours = Decimal(worked_minutes) / Decimal("60")
            days_value = worked_hours / Decimal("8")
            if is_holiday:
                days_value *= Decimal("1.5")
            cleaned_data["duration_hours"] = days_value.quantize(Decimal("0.1"))
        return cleaned_data


RecoveryLineFormSet = inlineformset_factory(
    StaffRequest,
    RecoveryLine,
    form=RecoveryLineForm,
    extra=1,
    can_delete=True,
)


class BaseRecoveryValidationMixin:
    @staticmethod
    def has_any_completed_line(formset):
        for form in formset.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            cleaned_data = form.cleaned_data
            if not cleaned_data:
                continue
            if any(
                cleaned_data.get(field)
                for field in [
                    "work_date",
                    "work_description",
                    "start_time",
                    "end_time",
                    "duration_hours",
                    "is_holiday",
                ]
            ):
                return True
        return False
