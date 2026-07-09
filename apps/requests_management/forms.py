from datetime import timedelta
from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from apps.personnel.models import Project
from apps.requests_management.models import RecoveryLine, StaffRequest


class AbsenceRequestForm(forms.ModelForm):
    DURATION_MODE_FULL_DAY = "full_day"
    DURATION_MODE_CUSTOM_HOURS = "custom_hours"
    SAME_DAY_DURATION_CHOICES = [
        (DURATION_MODE_FULL_DAY, "1 jour"),
        (DURATION_MODE_CUSTOM_HOURS, "Par heures"),
    ]
    WEEKEND_EXCLUSION_LABEL = "Exclure samedi et dimanche"

    duration_mode = forms.ChoiceField(
        label="Option pour une seule journee",
        required=False,
        choices=SAME_DAY_DURATION_CHOICES,
        initial=DURATION_MODE_FULL_DAY,
        widget=forms.RadioSelect,
    )
    exclude_weekends = forms.TypedChoiceField(
        label=WEEKEND_EXCLUSION_LABEL,
        required=False,
        choices=[
            ("1", "1"),
            ("0", "0"),
        ],
        coerce=lambda value: str(value) == "1",
        initial="1",
        widget=forms.HiddenInput,
    )

    def __init__(self, *args, profile=None, request_type=StaffRequest.TYPE_ABSENCE, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile
        self.request_type = request_type
        self.fields["duration_mode"].required = False
        self.fields["duration_mode"].initial = self._get_initial_duration_mode()
        self.fields["start_time"].required = False
        self.fields["end_time"].required = False
        self.fields["start_time"].widget.attrs["data-start-time"] = "1"
        self.fields["end_time"].widget.attrs["data-end-time"] = "1"
        self.fields["exclude_weekends"].required = False
        self.fields["exclude_weekends"].widget.attrs["data-exclude-weekends"] = "1"
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

    def _get_initial_duration_mode(self):
        raw_mode = self.data.get("duration_mode") if self.is_bound else None
        if raw_mode in {
            self.DURATION_MODE_FULL_DAY,
            self.DURATION_MODE_CUSTOM_HOURS,
        }:
            return raw_mode
        if getattr(self.instance, "start_time", None) and getattr(self.instance, "end_time", None):
            return self.DURATION_MODE_CUSTOM_HOURS
        return self.DURATION_MODE_FULL_DAY

    @staticmethod
    def _compute_same_day_duration(start_time, end_time):
        start_minutes = start_time.hour * 60 + start_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute
        if end_minutes <= start_minutes:
            raise forms.ValidationError("L'heure de fin doit etre apres l'heure de debut.")

        pause_start = 12 * 60
        pause_end = 13 * 60
        overlap = max(0, min(end_minutes, pause_end) - max(start_minutes, pause_start))
        worked_minutes = (end_minutes - start_minutes) - overlap
        if worked_minutes <= 0:
            raise forms.ValidationError("La plage horaire choisie ne couvre aucun temps de travail.")

        worked_hours = Decimal(worked_minutes) / Decimal("60")
        return (worked_hours / Decimal("8")).quantize(Decimal("0.1"))

    @staticmethod
    def _count_weekdays_inclusive(start_date, end_date):
        total_days = (end_date - start_date).days + 1
        business_days = 0
        for day_offset in range(total_days):
            current_date = start_date + timedelta(days=day_offset)
            if current_date.weekday() < 5:
                business_days += 1
        return business_days

    class Meta:
        model = StaffRequest
        fields = [
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "total_days",
            "reason",
            "remaining_days_for_reason",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "reason": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        duration_mode = cleaned_data.get("duration_mode") or self.DURATION_MODE_FULL_DAY
        exclude_weekends = cleaned_data.get("exclude_weekends")
        if self.is_bound and "exclude_weekends" not in self.data:
            exclude_weekends = True
        if exclude_weekends is None:
            exclude_weekends = True
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "La date de fin doit etre apres la date de debut.")
        elif start_date and end_date:
            if start_date == end_date:
                if exclude_weekends and start_date.weekday() >= 5:
                    self.add_error(
                        "start_date",
                        "La periode selectionnee ne contient aucun jour ouvrable.",
                    )
                    cleaned_data["total_days"] = Decimal("0.0")
                if duration_mode == self.DURATION_MODE_CUSTOM_HOURS:
                    if not start_time:
                        self.add_error("start_time", "Renseignez l'heure de debut.")
                    if not end_time:
                        self.add_error("end_time", "Renseignez l'heure de fin.")
                    if (
                        start_time
                        and end_time
                        and not self.has_error("start_date")
                        and not self.has_error("start_time")
                        and not self.has_error("end_time")
                    ):
                        try:
                            cleaned_data["total_days"] = self._compute_same_day_duration(
                                start_time,
                                end_time,
                            )
                        except forms.ValidationError as error:
                            self.add_error("end_time", error.message)
                else:
                    cleaned_data["start_time"] = None
                    cleaned_data["end_time"] = None
                    if not self.has_error("start_date"):
                        cleaned_data["total_days"] = Decimal("1.0")
            else:
                cleaned_data["start_time"] = None
                cleaned_data["end_time"] = None
                if exclude_weekends:
                    total_days = Decimal(str(self._count_weekdays_inclusive(start_date, end_date)))
                else:
                    total_days = Decimal((end_date - start_date).days + 1)
                cleaned_data["total_days"] = total_days
                if total_days <= Decimal("0.0"):
                    self.add_error(
                        "start_date",
                        "La periode selectionnee ne contient aucun jour ouvrable.",
                    )

        total_days = cleaned_data.get("total_days")

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
