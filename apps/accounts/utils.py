from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from apps.personnel.models import EmployeeProfile


def sync_profile_role(user, profile):
    if user.is_superuser and profile.role != EmployeeProfile.ROLE_ADMIN:
        profile.role = EmployeeProfile.ROLE_ADMIN
        profile.save(update_fields=["role", "updated_at"])
    elif user.is_staff and profile.role == EmployeeProfile.ROLE_USER:
        profile.role = EmployeeProfile.ROLE_ADMIN
        profile.save(update_fields=["role", "updated_at"])
    return profile


def get_user_profile(user):
    if not user.is_authenticated:
        return None
    profile, _ = EmployeeProfile.objects.get_or_create(user=user)
    return sync_profile_role(user, profile)


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            profile = get_user_profile(request.user)
            if not profile or profile.role not in allowed_roles:
                messages.error(request, "Vous n'avez pas acces a cette page.")
                return redirect("personnel:dashboard")
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
