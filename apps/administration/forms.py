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

        # --- Dynamic leave year fields (sliding window) ---
        from apps.personnel.leave_service import (
            get_annual_quota,
            get_leave_window_years,
        )

        self.leave_window_years = get_leave_window_years()
        self.annual_quota = get_annual_quota()

        for year in self.leave_window_years:
            field_name = f"leave_year_{year}"
            is_current = year == self.leave_window_years[-1]
            label = f"Congé {year}"
            if is_current:
                label += " (Bloqué jusqu'en %d)" % (year + 1)
            self.fields[field_name] = forms.DecimalField(
                label=label,
                max_digits=6,
                decimal_places=1,
                required=True,
                initial=self.annual_quota,
            )
            self.fields[field_name].help_text = (
                "Quota de congés pour cette année." if not is_current
                else "Droits de l'année en cours, non consommables avant l'année suivante."
            )
            self.fields[field_name].widget.attrs["placeholder"] = str(self.annual_quota)

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
                        "recovery_balance": self.profile.recovery_balance,
                        "role": self.profile.role,
                        "department": self.profile.department,
                    }
                )
                # Populate leave year fields with existing data
                from apps.personnel.models import AnnualLeave

                existing_leaves = {
                    al.year: al.quota for al in AnnualLeave.objects.filter(employee=self.profile)
                }
                for year in self.leave_window_years:
                    field_name = f"leave_year_{year}"
                    if year in existing_leaves:
                        self.initial[field_name] = existing_leaves[year]

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
        profile.recovery_balance = self.cleaned_data["recovery_balance"]
        profile.role = selected_role
        profile.department = self.cleaned_data["department"]
        if self.cleaned_data["photo"]:
            profile.photo = self.cleaned_data["photo"]
        profile.save()
        sync_profile_role(user, profile)

        # --- Save leave year balances ---
        from apps.personnel.leave_service import save_leave_balances_from_form

        year_balances = {}
        for year in self.leave_window_years:
            field_name = f"leave_year_{year}"
            year_balances[year] = self.cleaned_data.get(field_name, self.annual_quota)

        save_leave_balances_from_form(profile, year_balances)

        # --- Migrate recovery balance to AnnualRecovery ---
        from apps.personnel.recovery_service import migrate_recovery_balance

        migrate_recovery_balance(profile, self.cleaned_data["recovery_balance"])

        return user


class BrandingIdentityForm(forms.ModelForm):
    """Formulaire pour les paramètres d'identité et logo uniquement."""

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


class HRParamsForm(forms.ModelForm):
    """Formulaire pour les paramètres RH uniquement (congés, récupérations, photo)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "annual_leave_quota": "Quota annuel de conge",
            "leave_window_size": "Taille de la fenetre de conges",
            "absence_limit_enabled": "Activer la limite annuelle des absences",
            "absence_annual_limit": "Limite annuelle des absences",
            "recovery_limit_enabled": "Activer la limite annuelle des recuperations",
            "recovery_annual_limit": "Limite annuelle de recuperation",
            "profile_photo_editing_enabled": "Modification de la photo de profil par l'employe",
            "contact_enabled": "Activer les moyens de contact sur la page de connexion",
            "whatsapp_enabled": "Afficher WhatsApp sur la page de connexion",
            "whatsapp_number": "Numero WhatsApp",
            "email_contact_enabled": "Afficher Email sur la page de connexion",
            "email_contact": "Adresse email de contact",
            "telegram_enabled": "Afficher Telegram sur la page de connexion",
            "telegram_id": "Identifiant ou lien Telegram",
            "twitter_enabled": "Afficher Twitter / X sur la page de connexion",
            "twitter_url": "Lien du profil Twitter / X",
        }
        help_texts = {
            "annual_leave_quota": "Nombre de jours de conge acquis chaque annee civile. Les droits de l'annee en cours sont bloques jusqu'a l'annee suivante.",
            "leave_window_size": "Nombre d'annees conservees dans la fenetre glissante (ex: 3 = N-2, N-1, N).",
            "absence_limit_enabled": "Active ou desactive la limite annuelle d'absence pour tous les employes.",
            "absence_annual_limit": "Nombre maximum de jours d'absence qu'un employe peut accumuler par annee.",
            "recovery_limit_enabled": "Active ou desactive la limite annuelle de recuperation pour tous les employes.",
            "recovery_annual_limit": "Nombre maximum de jours de recuperation qu'un employe peut accumuler par annee.",
            "profile_photo_editing_enabled": "Active ou desactive la possibilite pour les employes de modifier leur photo de profil depuis leur interface.",
            "contact_enabled": "Affiche ou masque les moyens de contact (WhatsApp, email, Telegram, etc.) sur la page de connexion.",
            "whatsapp_enabled": "Affiche le bouton de contact WhatsApp sur la page de connexion.",
            "whatsapp_number": "Numero WhatsApp au format international (ex: +261 34 77 947 91).",
            "email_contact_enabled": "Affiche le bouton de contact par email sur la page de connexion.",
            "email_contact": "Adresse email utilisee pour le contact sur la page de connexion.",
            "telegram_enabled": "Affiche le bouton de contact Telegram sur la page de connexion.",
            "telegram_id": "Identifiant Telegram (ex: @centrevalbio) ou lien complet.",
            "twitter_enabled": "Affiche le bouton Twitter / X sur la page de connexion.",
            "twitter_url": "URL du profil Twitter / X (ex: https://x.com/centrevalbio).",
        }
        for field_name, label in labels.items():
            if field_name in self.fields:
                self.fields[field_name].label = label
        for field_name, help_text in help_texts.items():
            if field_name in self.fields:
                self.fields[field_name].help_text = help_text

    class Meta:
        model = LoginBranding
        fields = [
            "annual_leave_quota",
            "leave_window_size",
            "absence_limit_enabled",
            "absence_annual_limit",
            "recovery_limit_enabled",
            "recovery_annual_limit",
            "profile_photo_editing_enabled",
            "contact_enabled",
            "whatsapp_enabled",
            "whatsapp_number",
            "email_contact_enabled",
            "email_contact",
            "telegram_enabled",
            "telegram_id",
            "twitter_enabled",
            "twitter_url",
        ]


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
            "annual_leave_quota": "Quota annuel de conge",
            "leave_window_size": "Taille de la fenetre de conges",
            "leave_rules": "Regles generales de conges",
            "recovery_limit_enabled": "Activer la limite annuelle des recuperations",
            "recovery_annual_limit": "Limite annuelle de recuperation",
            "profile_photo_editing_enabled": "Modification de la photo de profil par l'employe",
            "logo_image": "Logo",
            "hero_image": "Illustration d'accueil",
        }
        help_texts = {
            "annual_leave_quota": "Nombre de jours de conge acquis chaque annee civile. Les droits de l'annee en cours sont bloques jusqu'a l'annee suivante.",
            "leave_window_size": "Nombre d'annees conservees dans la fenetre glissante (ex: 3 = N-2, N-1, N).",
            "leave_rules": "Regles generales affichees dans l'interface de gestion des conges.",
            "recovery_limit_enabled": "Active ou desactive la limite annuelle de recuperation pour tous les employes.",
            "recovery_annual_limit": "Nombre maximum de jours de recuperation qu'un employe peut accumuler par annee.",
            "profile_photo_editing_enabled": "Active ou desactive la possibilite pour les employes de modifier leur photo de profil depuis leur interface.",
        }
        for field_name, label in labels.items():
            if field_name in self.fields:
                self.fields[field_name].label = label
        for field_name, help_text in help_texts.items():
            if field_name in self.fields:
                self.fields[field_name].help_text = help_text

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
            "annual_leave_quota",
            "leave_window_size",
            "leave_rules",
            "recovery_limit_enabled",
            "recovery_annual_limit",
            "profile_photo_editing_enabled",
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
