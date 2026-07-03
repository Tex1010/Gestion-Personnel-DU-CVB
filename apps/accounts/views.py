from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.accounts.forms import LoginForm, StyledPasswordChangeForm
from apps.accounts.utils import get_user_profile
from apps.personnel.models import EmployeeProfile


def login_view(request):
    if request.user.is_authenticated:
        if request.session.get("portal_role") and request.session.get("portal_role") != EmployeeProfile.ROLE_USER:
            return redirect("administration:dashboard")
        return redirect("personnel:dashboard")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"],
        )
        if not user:
            messages.error(request, "Identifiants invalides.")
        else:
            profile = get_user_profile(user)
            selected_role = form.cleaned_data["role"]
            allowed_roles = {
                EmployeeProfile.ROLE_USER: [
                    EmployeeProfile.ROLE_USER,
                    EmployeeProfile.ROLE_ADMIN,
                    EmployeeProfile.ROLE_HIERARCHICAL,
                    EmployeeProfile.ROLE_DIRECTION,
                ],
                EmployeeProfile.ROLE_ADMIN: [EmployeeProfile.ROLE_ADMIN],
                EmployeeProfile.ROLE_HIERARCHICAL: [EmployeeProfile.ROLE_HIERARCHICAL],
                EmployeeProfile.ROLE_DIRECTION: [EmployeeProfile.ROLE_DIRECTION],
            }.get(selected_role, [EmployeeProfile.ROLE_USER])
            if user.username != "cvbadmin" and profile.role not in allowed_roles:
                messages.error(
                    request,
                    "Le role choisi ne correspond pas aux droits de ce compte.",
                )
            else:
                login(request, user)
                request.session["portal_role"] = selected_role
                messages.success(request, "Connexion reussie.")
                if selected_role != EmployeeProfile.ROLE_USER:
                    return redirect("administration:dashboard")
                return redirect("personnel:dashboard")

    return render(request, "accounts/login.html", {"form": form})


@login_required
def logout_view(request):
    if request.method != "POST":
        return redirect("personnel:dashboard")
    logout(request)
    messages.info(request, "Vous avez ete deconnecte.")
    return redirect("accounts:login")


@login_required
def password_change_view(request):
    form = StyledPasswordChangeForm(user=request.user, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Votre mot de passe a ete mis a jour.")
        if request.session.get("portal_role") and request.session.get("portal_role") != EmployeeProfile.ROLE_USER:
            return redirect("administration:dashboard")
        return redirect("personnel:dashboard")

    return render(request, "accounts/password_change.html", {"form": form})
