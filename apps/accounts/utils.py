from functools import wraps

from django.contrib import messages
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import redirect

from apps.personnel.models import ContractType, EmployeeProfile, Role


DEFAULT_ROLE_DEFINITIONS = [
    {
        "code": EmployeeProfile.ROLE_USER,
        "label_fr": "Employe",
        "label_en": "Employee",
        "label_mg": "Mpiasa",
        "portal": Role.PORTAL_EMPLOYEE,
        "show_in_login": True,
        "is_active": True,
        "is_system": True,
        "order": 10,
    },
    {
        "code": EmployeeProfile.ROLE_HIERARCHICAL,
        "label_fr": "Chef hierarchique",
        "label_en": "Line manager",
        "label_mg": "Lehiben'ny sampana",
        "portal": Role.PORTAL_ADMIN,
        "is_department_scoped": True,
        "can_validate_hierarchy": True,
        "show_in_login": True,
        "is_active": True,
        "is_system": True,
        "order": 20,
    },
    {
        "code": EmployeeProfile.ROLE_ADMIN,
        "label_fr": "Ressource Humain (RH)",
        "label_en": "Human Resources (HR)",
        "label_mg": "Ressource Humain (RH)",
        "portal": Role.PORTAL_ADMIN,
        "can_manage_settings": True,
        "can_validate_administration": True,
        "show_in_login": True,
        "is_active": True,
        "is_system": True,
        "order": 30,
    },
    {
        "code": EmployeeProfile.ROLE_DIRECTION,
        "label_fr": "Direction",
        "label_en": "Management",
        "label_mg": "Fitaleavana",
        "portal": Role.PORTAL_ADMIN,
        "can_validate_direction": True,
        "show_in_login": True,
        "is_active": True,
        "is_system": True,
        "order": 40,
    },
]

DEFAULT_CONTRACT_TYPE_DEFINITIONS = [
    {
        "code": EmployeeProfile.CONTRACT_TYPE_CDI,
        "label_fr": "CDI",
        "label_en": "Permanent contract",
        "label_mg": "Fifanekena maharitra",
        "is_active": True,
        "is_system": True,
        "order": 10,
    },
    {
        "code": EmployeeProfile.CONTRACT_TYPE_CDD,
        "label_fr": "CDD",
        "label_en": "Fixed-term contract",
        "label_mg": "Fifanekena voafetra",
        "is_active": True,
        "is_system": True,
        "order": 20,
    },
    {
        "code": EmployeeProfile.CONTRACT_TYPE_CONSULTANT,
        "label_fr": "Consultant",
        "label_en": "Consultant",
        "label_mg": "Mpanolotsaina",
        "is_active": True,
        "is_system": True,
        "order": 30,
    },
    {
        "code": EmployeeProfile.CONTRACT_TYPE_TEMPORARY,
        "label_fr": "Temporaire",
        "label_en": "Temporary",
        "label_mg": "Vonjimaika",
        "is_active": True,
        "is_system": True,
        "order": 40,
    },
]


def ensure_reference_data():
    try:
        for role_defaults in DEFAULT_ROLE_DEFINITIONS:
            role, created = Role.objects.get_or_create(
                code=role_defaults["code"],
                defaults=role_defaults,
            )
            # Keep system roles aligned with defaults when the app boots.
            # This ensures label updates (ex: Administration -> Ressource Humain (RH)) are applied
            # without requiring manual database edits.
            if (
                not created
                and getattr(role, "is_system", False)
                and role_defaults.get("code") == EmployeeProfile.ROLE_ADMIN
            ):
                update_fields = []
                for field_name in ["label_fr", "label_en", "label_mg"]:
                    new_value = role_defaults.get(field_name)
                    if new_value is not None and getattr(role, field_name) != new_value:
                        setattr(role, field_name, new_value)
                        update_fields.append(field_name)
                if update_fields:
                    role.save(update_fields=update_fields + ["updated_at"])
        for contract_defaults in DEFAULT_CONTRACT_TYPE_DEFINITIONS:
            ContractType.objects.get_or_create(
                code=contract_defaults["code"],
                defaults=contract_defaults,
            )
    except (OperationalError, ProgrammingError):
        return


def get_role_by_code(code):
    ensure_reference_data()
    return Role.objects.filter(code=code).first()


def get_contract_type_by_code(code):
    ensure_reference_data()
    return ContractType.objects.filter(code=code).first()


def get_role_code(profile):
    if not profile:
        return EmployeeProfile.ROLE_USER
    return profile.role_code


def get_role_portal(profile):
    if not profile:
        return Role.PORTAL_EMPLOYEE
    return profile.role_portal


def can_manage_settings(profile):
    return bool(profile and profile.can_manage_settings)


def can_access_approval_workflow(profile):
    if not profile:
        return False
    return any(
        [
            profile.can_validate_hierarchy,
            profile.can_validate_administration,
            profile.can_validate_direction,
            profile.can_manage_settings,
        ]
    )


def normalize_portal_role(portal_role):
    if portal_role in [Role.PORTAL_EMPLOYEE, Role.PORTAL_ADMIN]:
        return portal_role
    if portal_role == EmployeeProfile.ROLE_USER:
        return Role.PORTAL_EMPLOYEE
    if portal_role:
        return Role.PORTAL_ADMIN
    return Role.PORTAL_EMPLOYEE


def sync_profile_role(user, profile):
    ensure_reference_data()
    admin_role = get_role_by_code(EmployeeProfile.ROLE_ADMIN)
    employee_role = get_role_by_code(EmployeeProfile.ROLE_USER)
    if user.is_superuser and admin_role and profile.role_id != getattr(admin_role, "id", None):
        profile.role = admin_role
        profile.save(update_fields=["role", "updated_at"])
    elif user.is_staff and employee_role and profile.role_id == getattr(employee_role, "id", None):
        if admin_role:
            profile.role = admin_role
            profile.save(update_fields=["role", "updated_at"])
    elif not profile.role and employee_role:
        profile.role = employee_role
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
            if not profile or get_role_code(profile) not in allowed_roles:
                messages.error(request, "Vous n'avez pas acces a cette page.")
                return redirect("personnel:dashboard")
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def approval_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        profile = get_user_profile(request.user)
        if not can_access_approval_workflow(profile):
            messages.error(request, "Vous n'avez pas acces a cette page.")
            return redirect("personnel:dashboard")
        return view_func(request, *args, **kwargs)

    return wrapped


def settings_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        profile = get_user_profile(request.user)
        if not can_manage_settings(profile):
            messages.error(request, "Vous n'avez pas acces a cette page.")
            return redirect("personnel:dashboard")
        return view_func(request, *args, **kwargs)

    return wrapped
