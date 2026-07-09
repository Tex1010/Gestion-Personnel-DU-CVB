import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.administration.models import LoginBranding
from apps.mobile_api.models import MobileSessionToken
from apps.personnel.models import EmployeeProfile, Role
from apps.requests_management.models import StaffRequest


class MobileApiTests(TestCase):
    def setUp(self):
        self.employee_role = Role.objects.create(
            code=EmployeeProfile.ROLE_USER,
            label_fr="Employe",
            portal=Role.PORTAL_EMPLOYEE,
            show_in_login=True,
        )
        self.admin_role = Role.objects.create(
            code=EmployeeProfile.ROLE_ADMIN,
            label_fr="Administration",
            portal=Role.PORTAL_ADMIN,
            can_manage_settings=True,
            can_validate_administration=True,
            show_in_login=True,
        )
        self.employee_user = User.objects.create_user(
            username="agent",
            password="TestPass123!",
            first_name="Mamy",
            last_name="Agent",
        )
        self.employee_user.profile.role = self.employee_role
        self.employee_user.profile.leave_balance = 8
        self.employee_user.profile.recovery_balance = 3
        self.employee_user.profile.save()

        self.admin_user = User.objects.create_user(
            username="admin_mobile",
            password="TestPass123!",
            first_name="Aina",
            last_name="Admin",
        )
        self.admin_user.profile.role = self.admin_role
        self.admin_user.profile.save()

        self.branding = LoginBranding.objects.create(
            site_name="Portail Mobile CVB",
            subtitle="Gestion mobile du personnel",
            email="mobile@cvb.mg",
        )

    def _login(self, username, password, role):
        response = self.client.post(
            reverse("mobile_api:login"),
            data=json.dumps(
                {
                    "username": username,
                    "password": password,
                    "role": role,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["token"]

    def test_mobile_login_returns_token_and_branding(self):
        response = self.client.post(
            reverse("mobile_api:login"),
            data=json.dumps(
                {
                    "username": "agent",
                    "password": "TestPass123!",
                    "role": EmployeeProfile.ROLE_USER,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertIn("token", payload)
        self.assertEqual(
            payload["bootstrap"]["branding"]["site_name"],
            "Portail Mobile CVB",
        )
        self.assertEqual(MobileSessionToken.objects.count(), 1)

    def test_employee_dashboard_returns_summary(self):
        StaffRequest.objects.create(
            employee=self.employee_user.profile,
            request_type=StaffRequest.TYPE_ABSENCE,
            status=StaffRequest.STATUS_SUBMITTED,
            reason="Mission terrain",
            total_days=2,
        )
        token = self._login("agent", "TestPass123!", EmployeeProfile.ROLE_USER)

        response = self.client.get(
            reverse("mobile_api:dashboard"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["portal"], Role.PORTAL_EMPLOYEE)
        self.assertEqual(payload["summary"]["submitted_count"], 1)
        self.assertEqual(len(payload["recent_requests"]), 1)

    def test_admin_requests_pending_returns_actionable_items(self):
        StaffRequest.objects.create(
            employee=self.employee_user.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_ADMINISTRATION,
            reason="Conge annuel",
            total_days=5,
        )
        token = self._login(
            "admin_mobile",
            "TestPass123!",
            EmployeeProfile.ROLE_ADMIN,
        )

        response = self.client.get(
            f"{reverse('mobile_api:requests')}?kind=pending&portal=admin",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pending_count"], 1)
        self.assertEqual(len(payload["items"]), 1)

    def test_logout_invalidates_mobile_token(self):
        token = self._login("agent", "TestPass123!", EmployeeProfile.ROLE_USER)

        response = self.client.post(
            reverse("mobile_api:logout"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(MobileSessionToken.objects.count(), 0)
