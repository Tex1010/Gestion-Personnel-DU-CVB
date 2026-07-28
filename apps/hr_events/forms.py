from decimal import Decimal

from django import forms

from apps.common.business_validators import detect_hr_event_overlap
from apps.hr_events.models import HREvent
from apps.personnel.models import EmployeeProfile


class HREventForm(forms.ModelForm):
    DURATION_FULL_DAY = "full_day"
    DURATION_BY_HOURS = "by_hours"
    DURATION_CHOICES = [
        (DURATION_FULL_DAY, "Journee complete"),
        (DURATION_BY_HOURS, "Par heures"),
    ]

    duration_type = forms.ChoiceField(
        choices=DURATION_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "duration-type-radio"}),
        required=False,
        label="Type de duree",
    )

    class Meta:
        model = HREvent
        fields = [
            "employee",
            "event_type",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "days",
            "reason",
        ]
        widgets = {
            "employee": forms.Select(attrs={"class": "form-control tom-select-employee"}),
            "event_type": forms.Select(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control datepicker-input"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control datepicker-input"}),
            "start_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "end_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "days": forms.NumberInput(
                attrs={
                    "class": "form-control days-hidden-input",
                    "step": "0.001",
                    "min": "0",
                    "inputmode": "decimal",
                    "readonly": "readonly",
                }
            ),
            "reason": forms.Textarea(
                attrs={"rows": 3, "class": "form-control", "placeholder": "Motif / observations..."}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].label = "Employe"
        self.fields["employee"].queryset = EmployeeProfile.objects.select_related("user").exclude(
            user__username="cvbadmin"
        ).order_by("user__last_name", "user__first_name")
        self.fields["event_type"].label = "Type d'evenement"
        self.fields["start_date"].label = "Date debut"
        self.fields["end_date"].label = "Date fin"
        self.fields["start_time"].label = "Heure debut"
        self.fields["end_time"].label = "Heure fin"
        self.fields["days"].label = "Nombre de jours"
        self.fields["days"].disabled = True  # Always auto-calculated
        self.fields["reason"].label = "Motif / Observations"

        self.fields["start_date"].help_text = "Date de debut de l'evenement."
        self.fields["end_date"].help_text = "Date de fin de l'evenement (optionnel)."
        self.fields["start_time"].help_text = "Heure de debut (pour un evenement d'une seule journee)."
        self.fields["end_time"].help_text = "Heure de fin (pour un evenement d'une seule journee)."
        self.fields["days"].help_text = "Nombre de jours (calcule automatiquement)."
        self.fields["reason"].help_text = "Motif de l'evenement ou observations du RH."

        # If editing an existing event, set duration_type based on start_time/end_time
        if self.instance and self.instance.pk:
            if self.instance.start_time and self.instance.end_time:
                self.initial["duration_type"] = self.DURATION_BY_HOURS
            else:
                self.initial["duration_type"] = self.DURATION_FULL_DAY

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        duration_type = cleaned_data.get("duration_type")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        # Always recalculate, ignore submitted value
        days = None
        event_type = cleaned_data.get("event_type")

        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "La date de fin doit etre apres la date de debut.")

        # Calculate days for single-day events
        if start_date and end_date and start_date == end_date:
            if duration_type == self.DURATION_FULL_DAY:
                days = Decimal("1.0")
            elif duration_type == self.DURATION_BY_HOURS and start_time and end_time:
                days = self._calculate_partial_day_days(start_time, end_time)
            else:
                days = Decimal("0.0")
        elif start_date and end_date and end_date > start_date:
            # Multi-day event: count only weekdays, with partial first/last day if times provided
            days = self._calculate_multi_day_days(
                start_date, end_date,
                start_time if duration_type == self.DURATION_BY_HOURS else None,
                end_time if duration_type == self.DURATION_BY_HOURS else None,
                duration_type == self.DURATION_FULL_DAY,
            )

        if days is not None:
            cleaned_data["days"] = days

        if days is not None and days <= 0:
            self.add_error("days", "Le nombre de jours doit etre superieur a zero.")
            return cleaned_data

        if event_type == HREvent.TYPE_FAMILY_EVENT:
            employee = cleaned_data.get("employee")
            if employee and days is not None and days > 0:
                from apps.hr_events.hr_events_service import get_family_event_remaining

                remaining = get_family_event_remaining(employee)
                if remaining < days:
                    self.add_error(
                        "days",
                        f"Solde d'evenement familial insuffisant. "
                        f"Il reste {remaining} jour(s), vous demandez {days} jour(s).",
                    )

        # Overlap detection: prevent conflicting HR events for the same employee
        if (
            start_date
            and end_date
            and not self.has_error("start_date")
            and not self.has_error("end_date")
        ):
            employee = cleaned_data.get("employee")
            exclude_event_id = self.instance.pk if self.instance and self.instance.pk else None
            if employee:
                has_overlap, conflicting = detect_hr_event_overlap(
                    employee,
                    start_date,
                    end_date,
                    exclude_event_id=exclude_event_id,
                )
                if has_overlap:
                    self.add_error(
                        "start_date",
                        "Un evenement RH existe deja pour cette periode pour cet employe.",
                    )

        return cleaned_data

    @staticmethod
    def _calculate_partial_day_days(start_time, end_time):
        """Calculate days from start_time and end_time based on work schedule.

        Work schedule: 08:00-12:00 (morning), 13:00-17:00 (afternoon).
        Lunch break 12:00-13:00 is not counted.
        Full day = 8 hours = 480 minutes.
        """
        WORK_START_MORNING = 8 * 60    # 08:00 in minutes
        WORK_END_MORNING = 12 * 60     # 12:00 in minutes
        WORK_START_AFTERNOON = 13 * 60  # 13:00 in minutes
        WORK_END_AFTERNOON = 17 * 60    # 17:00 in minutes
        FULL_DAY_MINUTES = 8 * 60       # 8 hours = 480 minutes

        def to_minutes(time_value):
            if hasattr(time_value, "hour"):
                return time_value.hour * 60 + time_value.minute
            parts = time_value.split(":")
            return int(parts[0]) * 60 + int(parts[1])

        start_min = to_minutes(start_time)
        end_min = to_minutes(end_time)

        if end_min <= start_min:
            return Decimal("0.0")

        total_minutes = 0

        # Morning overlap (08:00-12:00)
        morning_start = max(start_min, WORK_START_MORNING)
        morning_end = min(end_min, WORK_END_MORNING)
        if morning_end > morning_start:
            total_minutes += morning_end - morning_start

        # Afternoon overlap (13:00-17:00)
        afternoon_start = max(start_min, WORK_START_AFTERNOON)
        afternoon_end = min(end_min, WORK_END_AFTERNOON)
        if afternoon_end > afternoon_start:
            total_minutes += afternoon_end - afternoon_start

        days = Decimal(str(total_minutes)) / Decimal(str(FULL_DAY_MINUTES))
        days = days.quantize(Decimal("0.001"))
        return days

    @staticmethod
    def _calculate_multi_day_days(start_date, end_date, start_time, end_time, is_full_day):
        """Calculate days for a multi-day period excluding weekends (Sat/Sun).

        If is_full_day is True, each weekday counts as 1.0 day.
        If start_time/end_time are provided (by_hours mode):
          - First day uses start_time as partial day
          - Last day uses end_time as partial day
          - Middle days count as full days (1.0 each)
        """
        from datetime import timedelta

        total_days = Decimal("0.0")
        current = start_date
        day_index = 0  # 0 = first day

        while current <= end_date:
            # Skip weekends (Monday=0, Sunday=6)
            if current.weekday() >= 5:  # Saturday=5, Sunday=6
                current += timedelta(days=1)
                day_index += 1
                continue

            if is_full_day:
                total_days += Decimal("1.0")
            else:
                is_first = (day_index == 0)
                is_last = (current == end_date)
                if is_first and start_time:
                    total_days += HREventForm._calculate_partial_day_days(start_time, "17:00")
                elif is_last and end_time:
                    total_days += HREventForm._calculate_partial_day_days("08:00", end_time)
                elif is_first and is_last and start_time and end_time:
                    total_days += HREventForm._calculate_partial_day_days(start_time, end_time)
                else:
                    total_days += Decimal("1.0")

            current += timedelta(days=1)
            day_index += 1

        return total_days