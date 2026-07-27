from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.utils import sync_profile_role
from apps.personnel.models import AnnualLeave, EmployeeProfile


@receiver(post_save, sender=User)
def ensure_employee_profile(sender, instance, created, **kwargs):
    if created:
        profile = EmployeeProfile.objects.create(user=instance)
        sync_profile_role(instance, profile)
        _ensure_initial_annual_leave(profile)


def _ensure_initial_annual_leave(profile):
    """
    Crée la fenêtre complète de congés (3 ans) à la création du profil.

    - Année courante (N) : bloquée (non consommable avant N+1)
    - Années N-1 et N-2 : créées avec quota complet (consommables)
    Utilise ensure_leave_window pour garantir la cohérence.
    """
    from apps.personnel.leave_service import ensure_leave_window

    ensure_leave_window(profile)
