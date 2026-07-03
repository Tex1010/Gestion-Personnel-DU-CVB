from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import PasswordChangeForm

from apps.personnel.models import EmployeeProfile


class LoginForm(forms.Form):
    role = forms.ChoiceField(
        label="Connexion en tant que",
        choices=[
            (EmployeeProfile.ROLE_USER, "Employé"),
            (EmployeeProfile.ROLE_ADMIN, "Administration"),
            (EmployeeProfile.ROLE_HIERARCHICAL, "Chef hiérarchique"),
            (EmployeeProfile.ROLE_DIRECTION, "Direction"),
        ],
        widget=forms.Select(
            attrs={
                "class": "form-select login-select-input",
                "data-login-role-select": "1",
            }
        ),
    )
    username = forms.CharField(
        label="Nom d'utilisateur",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "login-text-input",
                "placeholder": " ",
                "autocomplete": "username",
            }
        ),
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(
            attrs={
                "class": "login-text-input",
                "placeholder": " ",
                "autocomplete": "current-password",
            }
        ),
    )


class StyledPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(label="Mot de passe actuel", widget=forms.PasswordInput)
    new_password1 = forms.CharField(
        label="Nouveau mot de passe",
        widget=forms.PasswordInput,
        help_text=password_validation.password_validators_help_text_html(),
    )
    new_password2 = forms.CharField(
        label="Confirmation du nouveau mot de passe", widget=forms.PasswordInput
    )
