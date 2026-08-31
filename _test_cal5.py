import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.personnel.models import EmployeeProfile, Role
from apps.requests_management.models import StaffRequest
from decimal import Decimal
from datetime import date

User = get_user_model()

admin_role, _ = Role.objects.get_or_create(
    code=EmployeeProfile.ROLE_ADMIN,
    defaults={'label_fr': 'Administrateur', 'portal': Role.PORTAL_ADMIN, 'can_manage_settings': True}
)
employee_role, _ = Role.objects.get_or_create(
    code=EmployeeProfile.ROLE_USER,
    defaults={'label_fr': 'Employe', 'portal': Role.PORTAL_EMPLOYEE}
)

admin_user = User.objects.create_user(username='test_admin_cal_end', password='TestPass123!')
admin_user.profile.role = admin_role
admin_user.profile.save()

employee_user = User.objects.create_user(username='test_emp_cal_end', password='TestPass123!')
employee_user.profile.role = employee_role
employee_user.profile.save()

req = StaffRequest.objects.create(
    employee=employee_user.profile,
    request_type=StaffRequest.TYPE_LEAVE,
    status=StaffRequest.STATUS_APPROVED,
    start_date=date(2026, 3, 15),
    end_date=date(2026, 3, 20),
    total_days=Decimal('5'),
    reason='Test leave final end'
)

c = Client()
c.login(username='test_admin_cal_end', password='TestPass123!')
r = c.get(f'/admin-metier/calendrier/?year=2026&employee={employee_user.profile.id}')
content = r.content.decode()

print('status', r.status_code)
print('contains_employee_name', employee_user.profile.display_name in content)
print('contains_leave_reason', 'Test leave final end' in content)
print('contains_select', 'id="calendarEmployeeSelect"' in content)
print('contains_self_field', 'calendar-self-field' in content)
print('h1_admin', '<h1>Calendrier du personnel</h1>' in content)
print('h1_emp', '<h1>Mon calendrier</h1>' in content)
print('contains_months_grid', 'calendarMonthsGrid' in content)
print('contains_event_badge', 'has-events' in content)
