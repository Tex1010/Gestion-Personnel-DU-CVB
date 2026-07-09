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


class Role(models.Model):
    PORTAL_EMPLOYEE = "employee"
    PORTAL_ADMIN = "admin"

    PORTAL_CHOICES = [
        (PORTAL_EMPLOYEE, "Employe"),
        (PORTAL_ADMIN, "Ressource Humain (RH)"),
    ]

    code = models.SlugField(max_length=50, unique=True)
    label_fr = models.CharField(max_length=120)
    label_en = models.CharField(max_length=120, blank=True, default="")
    label_mg = models.CharField(max_length=120, blank=True, default="")
    portal = models.CharField(max_length=20, choices=PORTAL_CHOICES, default=PORTAL_EMPLOYEE)
    is_department_scoped = models.BooleanField(default=False)
    can_manage_settings = models.BooleanField(default=False)
    can_validate_hierarchy = models.BooleanField(default=False)
    can_validate_administration = models.BooleanField(default=False)
    can_validate_direction = models.BooleanField(default=False)
    show_in_login = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "label_fr"]
        verbose_name = "Role"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.label_fr

    def label_for(self, language):
        if language == "en":
            return self.label_en or self.label_fr
        if language == "mg":
            return self.label_mg or self.label_fr
        return self.label_fr


class ContractType(models.Model):
    code = models.SlugField(max_length=50, unique=True)
    label_fr = models.CharField(max_length=120)
    label_en = models.CharField(max_length=120, blank=True, default="")
    label_mg = models.CharField(max_length=120, blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "label_fr"]
        verbose_name = "Type de contrat"
        verbose_name_plural = "Types de contrat"

    def __str__(self):
        return self.label_fr

    def label_for(self, language):
        if language == "en":
            return self.label_en or self.label_fr
        if language == "mg":
            return self.label_mg or self.label_fr
        return self.label_fr


class EmployeeProfile(models.Model):
    ROLE_USER = "user"
    ROLE_ADMIN = "admin"
    ROLE_HIERARCHICAL = "hierarchical"
    ROLE_DIRECTION = "direction"

    CONTRACT_TYPE_CDI = "cdi"
    CONTRACT_TYPE_CDD = "cdd"
    CONTRACT_TYPE_CONSULTANT = "consultant"
    CONTRACT_TYPE_TEMPORARY = "temporary"

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
    contract_type = models.ForeignKey(
        ContractType,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="profiles",
        verbose_name="Type de contrat",
    )
    contract_end_date = models.DateField("Fin de contrat", blank=True, null=True)
    photo = models.FileField(upload_to="profiles/", blank=True, null=True)
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="profiles",
    )
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
        return self.role.label_fr if self.role else "Employe"

    @property
    def role_code(self):
        return self.role.code if self.role else self.ROLE_USER

    @property
    def role_portal(self):
        return self.role.portal if self.role else Role.PORTAL_EMPLOYEE

    @property
    def can_manage_settings(self):
        return bool(self.role and self.role.can_manage_settings)

    @property
    def can_validate_hierarchy(self):
        return bool(self.role and self.role.can_validate_hierarchy)

    @property
    def can_validate_administration(self):
        return bool(self.role and self.role.can_validate_administration)

    @property
    def can_validate_direction(self):
        return bool(self.role and self.role.can_validate_direction)

    @property
    def department_name(self):
        return self.department.name if self.department else "-"

    @property
    def contract_type_label(self):
        return self.contract_type.label_fr if self.contract_type else "-"

    @property
    def role_label_map(self):
        if not self.role:
            return {"fr": "Employe", "en": "Employee", "mg": "Mpiasa"}
        return {
            "fr": self.role.label_fr,
            "en": self.role.label_en or self.role.label_fr,
            "mg": self.role.label_mg or self.role.label_fr,
        }

    @property
    def contract_type_label_map(self):
        if not self.contract_type:
            return {"fr": "-", "en": "-", "mg": "-"}
        return {
            "fr": self.contract_type.label_fr,
            "en": self.contract_type.label_en or self.contract_type.label_fr,
            "mg": self.contract_type.label_mg or self.contract_type.label_fr,
        }
