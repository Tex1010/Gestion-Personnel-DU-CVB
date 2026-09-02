"""
Debug settings save with detailed output.
"""
from django.test import Client
from django.contrib.auth.models import User
from apps.personnel.models import EmployeeProfile, Role
from apps.administration.models import LoginBranding

er, _ = Role.objects.get_or_create(code='user', defaults={'label_fr': 'Employe', 'portal': Role.PORTAL_EMPLOYEE})
admin_role, _ = Role.objects.get_or_create(code='admin', defaults={'label_fr': 'Admin', 'portal': Role.PORTAL_ADMIN, 'can_manage_settings': True})
if not admin_role.can_manage_settings:
    admin_role.can_manage_settings = True
    admin_role.save()

admin, _ = User.objects.get_or_create(username='dash_test_admin', defaults={'password': 'TestPass123!'})
if not admin.has_usable_password():
    admin.set_password('TestPass123!')
admin.profile.role = admin_role
admin.profile.save()

branding = LoginBranding.objects.first()
if not branding:
    branding = LoginBranding.objects.create()

branding.contact_enabled = False
branding.whatsapp_enabled = False
branding.whatsapp_number = ""
branding.email_contact_enabled = False
branding.email_contact = ""
branding.telegram_enabled = False
branding.telegram_id = ""
branding.twitter_enabled = False
branding.twitter_url = ""
branding.save()

c = Client()
c.login(username='dash_test_admin', password='TestPass123!')

# First, GET the settings page to get CSRF token
r_get = c.get('/admin-metier/parametres/?panel=human_resources')
print('GET status:', r_get.status_code)

# Extract CSRF token
import re
csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r_get.content.decode())
csrf_token = csrf_match.group(1) if csrf_match else ''
print('CSRF token found:', bool(csrf_token))

# POST with CSRF token
post_data = {
    'csrfmiddlewaretoken': csrf_token,
    'save-hr-params': '1',
    'panel': 'human_resources',
    'annual_leave_quota': '30',
    'leave_window_size': '3',
    'absence_limit_enabled': 'on',
    'absence_annual_limit': '15',
    'recovery_limit_enabled': 'on',
    'recovery_annual_limit': '15',
    'profile_photo_editing_enabled': 'on',
    'contact_enabled': 'on',
    'whatsapp_enabled': 'on',
    'whatsapp_number': '+261 34 77 947 91',
    'email_contact_enabled': 'on',
    'email_contact': 'support@example.com',
    'telegram_enabled': 'on',
    'telegram_id': '@centrevalbio',
    'twitter_enabled': 'on',
    'twitter_url': 'https://x.com/centrevalbio',
}

r_post = c.post('/admin-metier/parametres/?panel=human_resources', post_data)
print('POST status:', r_post.status_code)
if r_post.status_code == 302:
    print('POST redirect:', r_post.headers.get('Location'))
    
    branding.refresh_from_db()
    print('\nAfter save:')
    print('contact_enabled:', branding.contact_enabled)
    print('whatsapp_enabled:', branding.whatsapp_enabled)
    print('whatsapp_number:', branding.whatsapp_number)
    print('email_contact_enabled:', branding.email_contact_enabled)
    print('email_contact:', branding.email_contact)
    print('telegram_enabled:', branding.telegram_enabled)
    print('telegram_id:', branding.telegram_id)
    print('twitter_enabled:', branding.twitter_enabled)
    print('twitter_url:', branding.twitter_url)
else:
    print('POST response:', r_post.content.decode()[:500])
