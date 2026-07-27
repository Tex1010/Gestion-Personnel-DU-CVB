from decimal import Decimal

from django import forms

from apps.hr_events.models import HREvent


class HREventForm(forms.ModelForm):
    class Meta:
        model = HREvent
        fields = [
            "employee",
            "event_type",
            "start_date",
            "end_date",
            "days",
            "reason",
        ]
        widgets = {
            "employee": forms.Select(attrs={"class": "form-control"}),
            "event_type": forms.Select(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "days": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.1",
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
        self.fields["days"].label = "Nombre de jours"
        self.fields["reason"].label = "Motif / Observations"

        self.fields["start_date"].help_text = "Date de debut de l'evenement."
        self.fields["end_date"].help_text = "Date de fin de l'evenement (optionnel)."
        self.fields["days"].help_text = "Nombre de jours (ex: 1.5)."
        self.fields["reason"].help_text = "Motif de l'evenement ou observations du RH."

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        days = cleaned_data.get("days")
        event_type = cleaned_data.get("event_type")

        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "La date de fin doit etre apres la date de debut.")

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
