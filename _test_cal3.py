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

u = User.objects.create_user(username='test_emp_cal_final', password='TestPass123!')
u.profile.role = employee_role
u.profile.save()

c = Client()
c.login(username='test_emp_cal_final', password='TestPass123!')
r = c.get('/mon-calendrier/')
content = r.content.decode()

print('select_in_html', 'id="calendarEmployeeSelect"' in content)
print('self_field', 'calendar-self-field' in content)
print('h1_emp', '<h1>Mon calendrier</h1>' in content)
print('h1_admin', '<h1>Calendrier du personnel</h1>' in content)
banners = re.findall(r'<div[^>]*class="calendar-no-selection-banner"', content)
print('banners found:', len(banners))
