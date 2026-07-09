from django import forms
from django.contrib.auth.models import User

from apps.accounts.utils import ensure_reference_data, get_role_by_code, sync_profile_role
from apps.administration.models import LoginBranding
from apps.personnel.models import ContractType, Department, EmployeeProfile, Project, Role


class EmployeeAccountForm(forms.Form):
    username = forms.CharField(label="Nom d'utilisateur", max_length=150)
    password = forms.CharField(label="Mot de passe initial", widget=forms.PasswordInput)
    first_name = forms.CharField(label="Nom", max_length=150)
    last_name = forms.CharField(label="Prenom", max_length=150)
    email = forms.EmailField(label="Email", required=False)
    employee_number = forms.CharField(label="Matricule", max_length=50, required=False)
    position = forms.CharField(label="Poste", max_length=150)
    contract_type = forms.ModelChoiceField(
        label="Type de contrat",
        queryset=ContractType.objects.none(),
        required=False,
        empty_label="Selectionner",
    )
    leave_balance = forms.DecimalField(label="Conge restant", initial=30)
    recovery_balance = forms.DecimalField(label="Recuperation restante", initial=0)
    role = forms.ModelChoiceField(
        label="Role",
        queryset=Role.objects.none(),
        empty_label=None,
    )
    department = forms.ModelChoiceField(
        label="Departement",
        queryset=Department.objects.filter(is_active=True),
        required=False,
    )
    photo = forms.FileField(label="Photo", required=False)

    def __init__(self, *args, profile=None, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)
        ensure_reference_data()
        help_texts = {
            "username": "Identifiant unique utilise pour la connexion de l'employe.",
            "password": "Definissez un mot de passe temporaire que l'employe pourra changer ensuite.",
            "first_name": "Nom de famille de l'employe.",
            "last_name": "Prenom de l'employe.",
            "email": "Optionnel. Utilise pour les notifications et les fiches personnelles.",
            "employee_number": "Optionnel. Renseignez le matricule interne si disponible.",
            "position": "Fonction ou poste affiche dans les tableaux et suivis.",
            "contract_type": "Choisissez un type de contrat actif parmi ceux definis dans les parametres.",
            "leave_balance": "Solde initial de conge attribue a ce compte.",
            "recovery_balance": "Solde initial de recuperation attribue a ce compte.",
            "role": "Determine l'espace d'acces et les permissions de l'employe.",
            "department": "Optionnel. Permet de rattacher l'employe a une structure existante.",
            "photo": "Optionnel. Photo de profil affichee dans l'interface.",
        }
        placeholders = {
            "username": "Ex: Tendry",
            "password": "Mot de passe temporaire",
            "first_name": "Ex: TENDRY",
            "last_name": "Ex: Tahinjanahary",
            "email": "Ex: tendry.it@valb.io",
            "employee_number": "Ex: CVB-001",
            "position": "Ex: Assistant administratif",
            "leave_balance": " 0",
            "recovery_balance": "0",
        }

        for field_name, help_text in help_texts.items():
            if field_name in self.fields:
                self.fields[field_name].help_text = help_text

        for field_name, placeholder in placeholders.items():
            if field_name in self.fields:
                self.fields[field_name].widget.attrs["placeholder"] = placeholder

        self.fields["contract_type"].queryset = ContractType.objects.filter(is_active=True).order_by(
            "order", "label_fr"
        )
        self.fields["role"].queryset = Role.objects.filter(is_active=True).order_by("order", "label_fr")
        self.fields["department"].queryset = Department.objects.filter(is_active=True).order_by("name")
        if self.profile:
            self.fields["password"].required = False
            self.fields["password"].widget = forms.PasswordInput(render_value=True)
            self.fields["password"].help_text = (
                "Laissez vide ou ******** pour conserver le mot de passe actuel."
            )
            if not self.is_bound:
                user = self.profile.user
                self.initial.update(
                    {
                        "username": user.username,
                        "password": "********",
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "email": user.email,
                        "employee_number": self.profile.employee_number,
                        "position": self.profile.position,
                        "contract_type": self.profile.contract_type,
                        "leave_balance": self.profile.leave_balance,
                        "recovery_balance": self.profile.recovery_balance,
                        "role": self.profile.role,
                        "department": self.profile.department,
                    }
                )

    def clean_password(self):
        password = self.cleaned_data["password"]
        if self.profile and password == "********":
            return ""
        return password

    def clean_username(self):
        username = self.cleaned_data["username"]
        queryset = User.objects.filter(username=username)
        if self.profile:
            queryset = queryset.exclude(pk=self.profile.user_id)
        if queryset.exists():
            raise forms.ValidationError("Ce nom d'utilisateur existe deja !")
        return username

    def save(self):
        if self.profile:
            user = self.profile.user
            user.username = self.cleaned_data["username"]
            password = self.cleaned_data["password"]
            if password:
                user.set_password(password)
        else:
            user = User.objects.create_user(
                username=self.cleaned_data["username"],
                password=self.cleaned_data["password"],
            )
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        selected_role = self.cleaned_data["role"]
        admin_role = get_role_by_code(EmployeeProfile.ROLE_ADMIN)
        user.is_staff = bool(admin_role and selected_role and selected_role.pk == admin_role.pk)
        user.is_superuser = False
        user.save()

        profile = user.profile
        profile.employee_number = self.cleaned_data["employee_number"]
        profile.position = self.cleaned_data["position"]
        profile.contract_type = self.cleaned_data["contract_type"]
        profile.leave_balance = self.cleaned_data["leave_balance"]
        profile.recovery_balance = self.cleaned_data["recovery_balance"]
        profile.role = selected_role
        profile.department = self.cleaned_data["department"]
        if self.cleaned_data["photo"]:
            profile.photo = self.cleaned_data["photo"]
        profile.save()
        sync_profile_role(user, profile)
        return user


class LoginBrandingForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "site_name": "Nom du site",
            "subtitle": "Sous-titre",
            "address": "Adresse",
            "email": "Email",
            "website": "Site web",
            "announcement": "Annonce",
            "request_submission_email_enabled": "Alertes email a la soumission",
            "logo_image": "Logo",
            "hero_image": "Illustration d'accueil",
        }
        for field_name, label in labels.items():
            if field_name in self.fields:
                self.fields[field_name].label = label
    class Meta:
        model = LoginBranding
        fields = [
            "site_name",
            "subtitle",
            "address",
            "email",
            "website",
            "announcement",
            "request_submission_email_enabled",
            "logo_image",
            "hero_image",
        ]

class DepartmentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "name": "Nom du departement",
            "code": "Code interne",
            "description": "Description",
            "is_active": "Departement actif",
        }
        help_texts = {
            "name": "Nom visible dans les comptes, filtres et tableaux.",
            "code": "Optionnel. Utilisez un code court pour faciliter le reperage.",
            "description": "Optionnel. Resume le perimetre ou la mission du departement.",
            "is_active": "Desactivez pour le retirer des choix sans supprimer l'historique existant.",
        }
        placeholders = {
            "name": "Ex: Ressource Humain",
            "code": "Ex: ADMIN",
            "description": "Ex: Gestion administrative et support interne",
        }

        for field_name, label in labels.items():
            if field_name in self.fields:
                self.fields[field_name].label = label

        for field_name, help_text in help_texts.items():
            if field_name in self.fields:
                self.fields[field_name].help_text = help_text

        for field_name, placeholder in placeholders.items():
            if field_name in self.fields:
                self.fields[field_name].widget.attrs["placeholder"] = placeholder

    class Meta:
        model = Department
        fields = ["name", "code", "description", "is_active"]


class RoleForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "code": "Code interne",
            "label_fr": "Libelle en francais",
            "label_en": "Libelle en anglais",
            "label_mg": "Libelle en malgache",
            "portal": "Espace d'acces",
            "is_department_scoped": "Limiter au departement",
            "can_manage_settings": "Acces aux parametres",
            "can_validate_hierarchy": "Validation chef hierarchique",
            "can_validate_administration": "Validation Ressource Humain (RH)",
            "can_validate_direction": "Validation direction",
            "show_in_login": "Visible a la connexion",
            "is_active": "Role actif",
            "order": "Ordre d'affichage",
        }
        help_texts = {
            "code": "Identifiant technique unique du role. Utilisez un mot simple, sans espace.",
            "label_fr": "Nom affiche par defaut dans l'application.",
            "label_en": "Optionnel. Utilise pour les affichages en anglais.",
            "label_mg": "Optionnel. Utilise pour les affichages en malgache.",
            "portal": "Choisissez l'espace dans lequel ce role sera utilise.",
            "is_department_scoped": "Activez cette option si ce role ne doit voir ou traiter que son departement.",
            "can_manage_settings": "Autorise l'acces au panneau Parametres.",
            "can_validate_hierarchy": "Permet de valider a l'etape chef hierarchique.",
            "can_validate_administration": "Permet de valider a l'etape Ressource Humain (RH).",
            "can_validate_direction": "Permet de valider a l'etape direction.",
            "show_in_login": "Affiche ce role dans l'ecran de connexion.",
            "is_active": "Desactivez pour masquer le role sans le supprimer.",
            "order": "Plus la valeur est petite, plus le role apparait en haut.",
        }
        placeholders = {
            "code": "Ex: chef-hierarchique",
            "label_fr": "Ex: Chef hierarchique",
            "label_en": "Ex: Line manager",
            "label_mg": "Ex: Tompon'andraikitra mivantana",
            "order": "0",
        }

        for field_name, label in labels.items():
            if field_name in self.fields:
                self.fields[field_name].label = label

        for field_name, help_text in help_texts.items():
            if field_name in self.fields:
                self.fields[field_name].help_text = help_text

        for field_name, placeholder in placeholders.items():
            if field_name in self.fields:
                self.fields[field_name].widget.attrs["placeholder"] = placeholder

        if "portal" in self.fields:
            self.fields["portal"].choices = [
                (Role.PORTAL_EMPLOYEE, "Employe"),
                (Role.PORTAL_ADMIN, "Ressource Humain (RH)"),
            ]

    class Meta:
        model = Role
        fields = [
            "code",
            "label_fr",
            "label_en",
            "label_mg",
            "portal",
            "is_department_scoped",
            "can_manage_settings",
            "can_validate_hierarchy",
            "can_validate_administration",
            "can_validate_direction",
            "show_in_login",
            "is_active",
            "order",
        ]


class ContractTypeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "code": "Code interne",
            "label_fr": "Libelle en francais",
            "label_en": "Libelle en anglais",
            "label_mg": "Libelle en malgache",
            "is_active": "Type actif",
            "order": "Ordre d'affichage",
        }
        help_texts = {
            "code": "Identifiant technique unique du type de contrat.",
            "label_fr": "Libelle principal affiche dans l'application.",
            "label_en": "Optionnel. Utilise pour l'affichage en anglais.",
            "label_mg": "Optionnel. Utilise pour l'affichage en malgache.",
            "is_active": "Desactivez pour masquer ce type dans les formulaires sans le supprimer.",
            "order": "Plus la valeur est petite, plus le type remonte dans les listes.",
        }
        placeholders = {
            "code": "Ex: consultant",
            "label_fr": "Ex: Consultant",
            "label_en": "Ex: Consultant",
            "label_mg": "Ex: Mpanolotsaina",
            "order": "0",
        }

        for field_name, label in labels.items():
            if field_name in self.fields:
                self.fields[field_name].label = label

        for field_name, help_text in help_texts.items():
            if field_name in self.fields:
                self.fields[field_name].help_text = help_text

        for field_name, placeholder in placeholders.items():
            if field_name in self.fields:
                self.fields[field_name].widget.attrs["placeholder"] = placeholder

    class Meta:
        model = ContractType
        fields = [
            "code",
            "label_fr",
            "label_en",
            "label_mg",
            "is_active",
            "order",
        ]


class ProjectForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "name": "Nom du projet",
            "code": "Code interne",
            "description": "Description",
            "is_active": "Projet actif",
        }
        help_texts = {
            "name": "Nom visible dans les demandes de recuperation.",
            "code": "Optionnel. Utilisez un code court pour les exports et suivis.",
            "description": "Optionnel. Resume l'objectif ou le contexte du projet.",
            "is_active": "Desactivez pour retirer le projet des nouvelles demandes sans perdre l'historique.",
        }
        placeholders = {
            "name": "Ex: Projet Biodiversite 2026",
            "code": "Ex: BIO-2026",
            "description": "Ex: Suivi des activites de terrain et collecte des donnees",
        }

        for field_name, label in labels.items():
            if field_name in self.fields:
                self.fields[field_name].label = label

        for field_name, help_text in help_texts.items():
            if field_name in self.fields:
                self.fields[field_name].help_text = help_text

        for field_name, placeholder in placeholders.items():
            if field_name in self.fields:
                self.fields[field_name].widget.attrs["placeholder"] = placeholder

    class Meta:
        model = Project
        fields = ["name", "code", "description", "is_active"]


class RequestReviewForm(forms.Form):
    admin_comment = forms.CharField(
        label="Commentaire admin",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Ajouter une remarque..."}),
    )
