content = '''from uuid import uuid4
from decimal import Decimal

from django.db import models

from apps.personnel.models import EmployeeProfile


class HREventQuerySet(models.QuerySet):
    def aggregate_total_days(self):
        """Calcule la somme des jours pour le queryset."""
        from decimal import Decimal as Dec

        result = self.aggregate(total=models.Sum("days"))
        total = result.get("total")
        if total is None:
            return Dec("0.0")
        return total


class HREventManager(models.Manager):
    def get_queryset(self):
        return HREventQuerySet(self.model, using=self._db)

    def aggregate_total_days(self):
        return self.get_queryset().aggregate_total_days()


class HREvent(models.Model):
    objects = HREventManager()
    """
    Gestion des evenements RH saisis par le service Ressource Humain (RH).

    Trois types d'evenements :
    - FAMILY_EVENT : consomme le solde "Evenement familial" (10 jours/an, reinitialise annuellement)
    - MEDICAL_LEAVE : augmente le total de repos medical (independant des autres soldes)
    - SICK_ABSENCE : augmente le total d'absence maladie (independant des autres soldes)

    Tous les evenements sont crees par le RH. Les employes ne voient que leurs totaux.
    """

    TYPE_FAMILY_EVENT = "family_event"
    TYPE_MEDICAL_LEAVE = "medical_leave"
    TYPE_SICK_ABSENCE = "sick_absence"

    TYPE_CHOICES = [
        (TYPE_FAMILY_EVENT, "Evenement familial"),
        (TYPE_MEDICAL_LEAVE, "Repos medical"),
        (TYPE_SICK_ABSENCE, "Absence maladie"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Actif"),
        (STATUS_CANCELLED, "Annule"),
    ]

    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.CASCADE,
        related_name="hr_events",
        verbose_name="Employe",
    )
    event_type = models.CharField(
        "Type d'evenement",
        max_length=20,
        choices=TYPE_CHOICES,
    )
    status = models.CharField(
        "Statut",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    start_date = models.DateField("Date debut", blank=True, null=True)
    end_date = models.DateField("Date fin", blank=True, null=True)
    start_time = models.TimeField("Heure debut", blank=True, null=True)
    end_time = models.TimeField("Heure fin", blank=True, null=True)
    days = models.DecimalField(
        "Nombre de jours",
        max_digits=6,
        decimal_places=1,
        default=Decimal("0.0"),
    )
    reason = models.TextField("Motif / Observations", blank=True)
    created_at = models.DateTimeField("Date de creation", auto_now_add=True)
    updated_at = models.DateTimeField("Date de mise a jour", auto_now=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hr_events_created",
        verbose_name="Cree par",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Evenement RH"
        verbose_name_plural = "Evenements RH"

    def __str__(self):
        return f"{self.get_event_type_display()} - {self.employee.display_name} ({self.days} jours)"

    @property
    def type_label(self):
        return self.get_event_type_display()

    @property
    def status_label(self):
        return self.get_status_display()

    @property
    def is_active(self):
        return self.status == self.STATUS_ACTIVE

    @property
    def can_cancel(self):
        """
        Un evenement peut etre annule s'il a ete cree il y a moins de 24 heures.
        """
        from django.utils import timezone

        if not self.is_active:
            return False
        if not self.created_at:
            return False
        return (timezone.now() - self.created_at) <= timezone.timedelta(hours=24)

    @property
    def display_days(self):
        """Affiche les jours sans les zeros inutiles."""
        formatted = format(self.days, "f").rstrip("0").rstrip(".")
        return formatted or "0"

    @property
    def period_label(self):
        from django.utils import timezone

        def fmt(date_value):
            return date_value.strftime("%d/%m/%Y") if date_value else "-"

        start_label = fmt(self.start_date)
        if self.start_date and self.end_date and self.start_date == self.end_date:
            return start_label
        if self.start_date and self.end_date:
            return f"{start_label} - {fmt(self.end_date)}"
        if self.start_date:
            return start_label
        return "-"
'''

with open('apps/hr_events/models.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("models.py written successfully")
