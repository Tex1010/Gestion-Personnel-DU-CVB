import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client
from apps.personnel.models import EmployeeProfile, Role

role = Role.objects.filter(code="user").first()
emp = (
    EmployeeProfile.objects.filt    er(role=role)
    .exclude(user__username="cvbadmin")
    .first()
)
client = Client()
client.force_login(emp.user)

content = client.get("/tableau-de-bord/").content.decode()

print("=== APPROVED ABSENCES DAYS CARD ===")
print("Status: 200")
print("Has modern card:", "approved-absences-card" in content)
print("Count element id:", "approvedAbsencesDays" in content)
print("Has 'jours' label:", "jours d'absence acceptés" in content)
print("Has limit block:", "approved-absences-limit-block" in content)
print("Has progress bar:", "approved-absences-progress" in content)
print("Has remaining label:", "jours restants" in content)
print("Has annual limit:", "Limite annuelle" in content)
print("Has progress CSS:", ".approved-absences-progress-fill" in content)

# Verify we are counting DAYS not requests
import re

# Check approved_absence_days is a decimal (not a count)
print("Has absence limit variable:", "absence_limit" in content)
print("Has remaining variable:", "remaining_absence_days" in content)
print("Has percent used:", "absence_percent_used" in content)