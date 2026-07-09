from django import forms
from django.contrib.auth.forms import PasswordChangeForm

from apps.accounts.utils import ensure_reference_data
from apps.personnel.models import Role


class LoginForm(forms.Form):
    role = forms.ChoiceField(
        label="Connexion en tant que",
        choices=[],
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ensure_reference_data()
        login_roles = Role.objects.filter(is_active=True, show_in_login=True).order_by("order", "label_fr")
        self.fields["role"].choices = [(role.code, role.label_fr) for role in login_roles]
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
    old_password = forms.CharField(
        label="Mot de passe actuel",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "data-password-current": "1",
            }
        ),
        help_text="Utilisez le mot de passe actif de votre compte pour autoriser cette modification.",
    )
    new_password1 = forms.CharField(
        label="Nouveau mot de passe",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "data-password-new": "1",
            }
        ),
        help_text=(
            "<ul class='password-rule-list'>"
            "<li>Au moins 8 caracteres.</li>"
            "<li>Evitez les informations trop proches de votre identite.</li>"
            "<li>Ne choisissez pas un mot de passe trop commun.</li>"
            "<li>Le mot de passe ne peut pas etre uniquement numerique.</li>"
            "</ul>"
        ),
    )
    new_password2 = forms.CharField(
        label="Confirmation du nouveau mot de passe",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "data-password-confirm": "1",
            }
        ),
        help_text="Retapez exactement le nouveau mot de passe pour valider sans erreur de saisie.",
    )
