import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.personnel.models import EmployeeProfile, Role
import re

User = get_user_model()

employee_role, _ = Role.objects.get_or_create(
    code=EmployeeProfile.ROLE_USER,
    defaults={'label_fr': 'Employe', 'portal': Role.PORTAL_EMPLOYEE}
)

u = User.objects.create_user(username='test_emp_cal12', password='TestPass123!')
u.profile.role = employee_role
u.profile.save()

c = Client()
c.login(username='test_emp_cal12', password='TestPass123!')
r = c.get('/mon-calendrier/')
content = r.content.decode()

# Check if the banner div is actually in the HTML
banners = re.findall(r'<div[^>]*class="calendar-no-selection-banner"', content)
print('banners found:', len(banners))

# Check for the text inside the banner in HTML
has_banner_text = 'Veuillez sélectionner un employé pour afficher son calendrier.' in content
print('has_banner_text:', has_banner_text)

# Show snippet around the banner text if found
idx = content.find('Veuillez sélectionner')
if idx != -1:
    print('snippet:', content[idx-50:idx+200])
else:
    print('banner text NOT found')
