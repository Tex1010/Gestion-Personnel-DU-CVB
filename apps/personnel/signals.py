from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.utils import sync_profile_role
from apps.personnel.models import EmployeeProfile


@receiver(post_save, sender=User)
def ensure_employee_profile(sender, instance, created, **kwargs):
    if created:
        profile = EmployeeProfile.objects.create(user=instance)
        sync_profile_role(instance, profile)
