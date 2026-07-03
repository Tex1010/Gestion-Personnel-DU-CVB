from decimal import Decimal

from django.db import models

from apps.personnel.models import EmployeeProfile


class StaffRequest(models.Model):
    TYPE_LEAVE = "leave"
    TYPE_ABSENCE = "absence"
    TYPE_RECOVERY = "recovery"

    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    APPROVAL_HIERARCHY = "hierarchy"
    APPROVAL_ADMINISTRATION = "administration"
    APPROVAL_DIRECTION = "direction"
    APPROVAL_COMPLETED = "completed"

    REQUEST_TYPE_CHOICES = [
        (TYPE_LEAVE, "Conge"),
        (TYPE_ABSENCE, "Absence"),
        (TYPE_RECOVERY, "Recuperation"),
    ]
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Brouillon"),
        (STATUS_SUBMITTED, "Soumise"),
        (STATUS_APPROVED, "Approuvee"),
        (STATUS_REJECTED, "Rejetee"),
    ]
    APPROVAL_STAGE_CHOICES = [
        (APPROVAL_HIERARCHY, "Chef hierarchique"),
        (APPROVAL_ADMINISTRATION, "Administration"),
        (APPROVAL_DIRECTION, "Direction"),
        (APPROVAL_COMPLETED, "Terminee"),
    ]

    employee = models.ForeignKey(
        EmployeeProfile, on_delete=models.CASCADE, related_name="requests"
    )
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_SUBMITTED
    )
    approval_stage = models.CharField(
        max_length=20,
        choices=APPROVAL_STAGE_CHOICES,
        default=APPROVAL_HIERARCHY,
        verbose_name="Etape d'approbation",
    )
    project_name = models.CharField("Projet", max_length=150, blank=True)
    start_date = models.DateField("Date debut", blank=True, null=True)
    end_date = models.DateField("Date fin", blank=True, null=True)
    total_days = models.DecimalField(
        "Total jours", max_digits=6, decimal_places=1, default=0
    )
    remaining_days_for_reason = models.DecimalField(
        "Jours restants pour le motif", max_digits=6, decimal_places=1, default=0
    )
    reason = models.TextField("Motif", blank=True)
    admin_comment = models.TextField("Commentaire admin", blank=True)
    hierarchical_signature = models.CharField(max_length=120, blank=True)
    administration_signature = models.CharField(max_length=120, blank=True)
    direction_signature = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Demande"
        verbose_name_plural = "Demandes"

    def __str__(self):
        return f"{self.get_request_type_display()} - {self.employee.display_name}"

    @property
    def type_label(self):
        return self.get_request_type_display()

    @property
    def status_label(self):
        return self.get_status_display()

    def compute_recovery_hours(self):
        total_hours = sum(line.duration_hours for line in self.recovery_lines.all())
        return round(total_hours, 2)


class RecoveryLine(models.Model):
    request = models.ForeignKey(
        StaffRequest, on_delete=models.CASCADE, related_name="recovery_lines"
    )
    work_date = models.DateField("Date")
    work_description = models.CharField("Nature de travaux", max_length=255)
    start_time = models.TimeField("Debut heure")
    end_time = models.TimeField("Fin d'heure")
    duration_hours = models.DecimalField(
        "Duree", max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    is_holiday = models.BooleanField("Ferie", default=False)

    class Meta:
        ordering = ["work_date", "start_time"]
        verbose_name = "Ligne de recuperation"
        verbose_name_plural = "Lignes de recuperation"

    def __str__(self):
        return f"{self.work_date} - {self.work_description}"
