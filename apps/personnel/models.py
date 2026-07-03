from django.contrib.auth.models import User
from django.db import models


class Department(models.Model):
    name = models.CharField("Nom du departement", max_length=120, unique=True)
    code = models.CharField("Code", max_length=20, blank=True)
    description = models.TextField("Description", blank=True)
    is_active = models.BooleanField("Actif", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Departement"
        verbose_name_plural = "Departements"

    def __str__(self):
        return self.name


class Project(models.Model):
    name = models.CharField("Nom du projet", max_length=160, unique=True)
    code = models.CharField("Code", max_length=30, blank=True)
    description = models.TextField("Description", blank=True)
    is_active = models.BooleanField("Actif", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Projet"
        verbose_name_plural = "Projets"

    def __str__(self):
        return self.name


class EmployeeProfile(models.Model):
    ROLE_USER = "user"
    ROLE_ADMIN = "admin"
    ROLE_HIERARCHICAL = "hierarchical"
    ROLE_DIRECTION = "direction"

    CONTRACT_TYPE_CDI = "cdi"
    CONTRACT_TYPE_CDD = "cdd"
    CONTRACT_TYPE_CONSULTANT = "consultant"
    CONTRACT_TYPE_TEMPORARY = "temporary"

    CONTRACT_TYPE_CHOICES = [
        (CONTRACT_TYPE_CDI, "CDI"),
        (CONTRACT_TYPE_CDD, "CDD"),
        (CONTRACT_TYPE_CONSULTANT, "Consultant"),
        (CONTRACT_TYPE_TEMPORARY, "Temporaire"),
    ]

    ROLE_CHOICES = [
        (ROLE_USER, "Employe"),
        (ROLE_ADMIN, "Admin"),
        (ROLE_HIERARCHICAL, "Chef hierarchique"),
        (ROLE_DIRECTION, "Direction"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        related_name="employees",
        blank=True,
        null=True,
        verbose_name="Departement",
    )
    employee_number = models.CharField("Matricule", max_length=50, blank=True)
    position = models.CharField("Poste", max_length=150, blank=True)
    contract_type = models.CharField(
        "Type de contrat",
        max_length=20,
        choices=CONTRACT_TYPE_CHOICES,
        blank=True,
        default="",
    )
    contract_end_date = models.DateField("Fin de contrat", blank=True, null=True)
    photo = models.FileField(upload_to="profiles/", blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_USER)
    leave_balance = models.DecimalField(
        "Solde de conge", max_digits=6, decimal_places=1, default=30
    )
    recovery_balance = models.DecimalField(
        "Solde de recuperation", max_digits=6, decimal_places=1, default=0
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__first_name", "user__last_name", "user__username"]
        verbose_name = "Profil employe"
        verbose_name_plural = "Profils employes"

    def __str__(self):
        return self.full_name or self.user.username

    @property
    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}".strip()

    @property
    def display_name(self):
        return self.full_name or self.user.username

    @property
    def dashboard_role_label(self):
        return dict(self.ROLE_CHOICES).get(self.role, self.role)

    @property
    def department_name(self):
        return self.department.name if self.department else "-"

    @property
    def contract_type_label(self):
        return dict(self.CONTRACT_TYPE_CHOICES).get(self.contract_type, "-")
