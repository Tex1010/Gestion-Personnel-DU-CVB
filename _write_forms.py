form_content = r'''from decimal import Decimal

from django import forms

from apps.hr_events.models import HREvent


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
            "employee": forms.Select(attrs={"class": "form-control"}),
            "event_type": forms.Select(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "start_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "end_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "days": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.001",
                    "min": "0",
                    "inputmode": "decimal",
                }
            ),
            "reason": forms.Textarea(
                attrs={"rows": 3, "class": "form-control", "placeholder": "Motif / observations..."}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].label = "Employe"
        self.fields["event_type"].label = "Type d'evenement"
        self.fields["start_date"].label = "Date debut"
        self.fields["end_date"].label = "Date fin"
        self.fields["start_time"].label = "Heure debut"
        self.fields["end_time"].label = "Heure fin"
        self.fields["days"].label = "Nombre de jours"
        self.fields["reason"].label = "Motif / Observations"

        self.fields["start_date"].help_text = "Date de debut de l'evenement."
        self.fields["end_date"].help_text = "Date de fin de l'evenement (optionnel)."
        self.fields["start_time"].help_text = "Heure de debut (pour un evenement d'une seule journee)."
        self.fields["end_time"].help_text = "Heure de fin (pour un evenement d'une seule journee)."
        self.fields["days"].help_text = "Nombre de jours (calcule automatiquement pour un evenement d'une seule journee)."
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
        days = cleaned_data.get("days")
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
            cleaned_data["days"] = days

        if days is not None and days <= 0:
            self.add_error("days", "Le nombre de jours doit etre superieur a zero.")

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
'''

with open('apps/hr_events/forms.py', 'w', encoding='utf-8') as f:
    f.write(form_content)

print("forms.py written successfully")
