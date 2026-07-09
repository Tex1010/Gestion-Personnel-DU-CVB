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
    STATUS_CANCELLED = "cancelled"

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
        (STATUS_CANCELLED, "Annulee"),
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
    start_time = models.TimeField("Heure debut", blank=True, null=True)
    end_time = models.TimeField("Heure fin", blank=True, null=True)
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
        if self.status == self.STATUS_CANCELLED:
            return "Annuler"
        return self.get_status_display()

    @property
    def employee_status_label(self):
        if self.status == self.STATUS_DRAFT:
            return "Brouillon"
        if self.status == self.STATUS_REJECTED:
            return "Rejetee"
        if self.status == self.STATUS_APPROVED or self.approval_stage == self.APPROVAL_COMPLETED:
            return "Approuvee"
        if self.approval_stage == self.APPROVAL_HIERARCHY:
            return "En attente du chef hierarchique"
        if self.approval_stage == self.APPROVAL_ADMINISTRATION:
            return "Chef hierarchique approuve, attente administration"
        if self.approval_stage == self.APPROVAL_DIRECTION:
            return "Chef hierarchique et administration approuves, attente direction"
        return self.get_status_display()

    @property
    def employee_status_badge_class(self):
        if self.status == self.STATUS_DRAFT:
            return "draft"
        if self.status == self.STATUS_REJECTED:
            return "rejected"
        if self.status == self.STATUS_APPROVED or self.approval_stage == self.APPROVAL_COMPLETED:
            return "approved"
        if self.approval_stage == self.APPROVAL_HIERARCHY:
            return "pending-hierarchy"
        if self.approval_stage == self.APPROVAL_ADMINISTRATION:
            return "approved-hierarchy"
        if self.approval_stage == self.APPROVAL_DIRECTION:
            return "approved-administration"
        return self.status

    @property
    def employee_simple_status_label(self):
        if self.status == self.STATUS_REJECTED:
            return "Refusee"
        if self.status == self.STATUS_CANCELLED:
            return "Annulee"
        if self.status == self.STATUS_APPROVED or self.approval_stage == self.APPROVAL_COMPLETED:
            return "Approuvee"
        return "En attente"

    @property
    def employee_simple_status_badge_class(self):
        if self.employee_simple_status_label == "Approuvee":
            return "approved"
        if self.employee_simple_status_label == "Refusee":
            return "rejected"
        if self.employee_simple_status_label == "Annulee":
            return "cancelled"
        return "stage-pending"

    def _approval_status_for_stage(self, stage):
        if self.status == self.STATUS_DRAFT:
            return "En attente"

        stage_order = {
            self.APPROVAL_HIERARCHY: 1,
            self.APPROVAL_ADMINISTRATION: 2,
            self.APPROVAL_DIRECTION: 3,
            self.APPROVAL_COMPLETED: 4,
        }
        current_order = stage_order.get(self.approval_stage, 0)
        target_order = stage_order.get(stage, 0)

        if self.status == self.STATUS_APPROVED or self.approval_stage == self.APPROVAL_COMPLETED:
            return "Approuvee"

        if self.status == self.STATUS_REJECTED:
            if self.approval_stage == stage:
                return "Refusee"
            if current_order > target_order:
                return "Approuvee"
            return "En attente"

        if current_order > target_order:
            return "Approuvee"
        if current_order == target_order:
            return "En attente"
        return "En attente"

    def _approval_badge_class_for_stage(self, stage):
        label = self._approval_status_for_stage(stage)
        if label == "Approuvee":
            return "stage-approved"
        if label == "Refusee":
            return "stage-rejected"
        return "stage-pending"

    @property
    def hierarchy_status_label(self):
        return self._approval_status_for_stage(self.APPROVAL_HIERARCHY)

    @property
    def hierarchy_status_badge_class(self):
        return self._approval_badge_class_for_stage(self.APPROVAL_HIERARCHY)

    @property
    def administration_status_label(self):
        return self._approval_status_for_stage(self.APPROVAL_ADMINISTRATION)

    @property
    def administration_status_badge_class(self):
        return self._approval_badge_class_for_stage(self.APPROVAL_ADMINISTRATION)

    @property
    def direction_status_label(self):
        return self._approval_status_for_stage(self.APPROVAL_DIRECTION)

    @property
    def direction_status_badge_class(self):
        return self._approval_badge_class_for_stage(self.APPROVAL_DIRECTION)

    @staticmethod
    def _format_date(value):
        return value.strftime("%d/%m/%Y") if value else "-"

    @staticmethod
    def _format_time(value):
        return value.strftime("%H:%M") if value else "-"

    @property
    def has_custom_time_range(self):
        return bool(
            self.start_date
            and self.end_date
            and self.start_date == self.end_date
            and self.start_time
            and self.end_time
        )

    @property
    def period_entries(self):
        if self.request_type == self.TYPE_RECOVERY:
            entries = [
                (
                    f"{self._format_date(line.work_date)} "
                    f"{self._format_time(line.start_time)} - {self._format_time(line.end_time)}"
                )
                for line in self.recovery_lines.all()
            ]
            return entries or ["-"]

        start_label = self._format_date(self.start_date) if self.start_date else "-"
        if self.has_custom_time_range:
            return [
                (
                    f"{start_label} "
                    f"{self._format_time(self.start_time)} - {self._format_time(self.end_time)}"
                )
            ]
        if self.start_date and self.end_date and self.start_date == self.end_date:
            return [start_label]
        if self.end_date:
            return [f"{start_label} - {self._format_date(self.end_date)}"]
        return [start_label]

    @property
    def period_label(self):
        return " | ".join(self.period_entries)

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
