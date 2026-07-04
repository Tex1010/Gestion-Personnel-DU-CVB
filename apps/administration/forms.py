from django import forms
from django.contrib.auth.models import User

from apps.accounts.utils import sync_profile_role
from apps.administration.models import LoginBranding
from apps.personnel.models import Department, EmployeeProfile, Project


class EmployeeAccountForm(forms.Form):
    username = forms.CharField(label="Nom d'utilisateur", max_length=150)
    password = forms.CharField(label="Mot de passe initial", widget=forms.PasswordInput)
    first_name = forms.CharField(label="Nom", max_length=150)
    last_name = forms.CharField(label="Prenom", max_length=150)
    email = forms.EmailField(label="Email", required=False)
    employee_number = forms.CharField(label="Matricule", max_length=50, required=False)
    position = forms.CharField(label="Poste", max_length=150)
    contract_type = forms.ChoiceField(
        label="Type de contrat",
        choices=[("", "Sélectionner")] + list(EmployeeProfile.CONTRACT_TYPE_CHOICES),
        required=False,
    )
    leave_balance = forms.DecimalField(label="Conge restant", initial=30)
    recovery_balance = forms.DecimalField(label="Recuperation restante", initial=0)
    role = forms.ChoiceField(label="Role", choices=EmployeeProfile.ROLE_CHOICES)
    department = forms.ModelChoiceField(
        label="Departement",
        queryset=Department.objects.filter(is_active=True),
        required=False,
    )
    photo = forms.FileField(label="Photo", required=False)

    def __init__(self, *args, profile=None, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = list(EmployeeProfile.ROLE_CHOICES)
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
            raise forms.ValidationError("Ce nom d'utilisateur existe deja.")
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
        user.is_staff = selected_role == EmployeeProfile.ROLE_ADMIN
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
    class Meta:
        model = Department
        fields = ["name", "code", "description", "is_active"]


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "code", "description", "is_active"]


class RequestReviewForm(forms.Form):
    admin_comment = forms.CharField(
        label="Commentaire admin",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Ajouter une remarque..."}),
    )
