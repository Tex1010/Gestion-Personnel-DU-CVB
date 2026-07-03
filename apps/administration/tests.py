import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.administration.models import AccountActionHistory, RequestActionHistory
from apps.personnel.models import EmployeeProfile
from apps.requests_management.models import StaffRequest


class AdministrationViewsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="TestPass123!")
        self.admin.is_staff = True
        self.admin.save()
        self.admin.profile.role = EmployeeProfile.ROLE_ADMIN
        self.admin.profile.recovery_balance = Decimal("5.0")
        self.admin.profile.save()
        self.client.login(username="admin", password="TestPass123!")

        self.employee = User.objects.create_user(
            username="agent",
            password="TestPass123!",
            first_name="Mamy",
            last_name="Agent",
        )
        self.employee.profile.role = EmployeeProfile.ROLE_USER
        self.employee.profile.position = "Technicien"
        self.employee.profile.leave_balance = Decimal("10.0")
        self.employee.profile.recovery_balance = Decimal("6.0")
        self.employee.profile.save()

        self.employee_to_delete = User.objects.create_user(
            username="agent_delete",
            password="TestPass123!",
        )
        self.employee_to_delete.profile.role = EmployeeProfile.ROLE_USER
        self.employee_to_delete.profile.leave_balance = Decimal("4.0")
        self.employee_to_delete.profile.recovery_balance = Decimal("4.0")
        self.employee_to_delete.profile.save()

    def test_admin_dashboard_requires_admin_role(self):
        user = User.objects.create_user(username="simple", password="TestPass123!")
        user.profile.role = EmployeeProfile.ROLE_USER
        user.profile.save()
        self.client.login(username="simple", password="TestPass123!")

        response = self.client.get(reverse("administration:dashboard"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "acces a cette page")

    def test_admin_dashboard_exposes_low_balance_metrics_and_distributions(self):
        low_balance_user = User.objects.create_user(
            username="agent_low",
            password="TestPass123!",
            first_name="Bodo",
            last_name="Petit",
        )
        low_balance_user.profile.role = EmployeeProfile.ROLE_USER
        low_balance_user.profile.leave_balance = Decimal("1.5")
        low_balance_user.profile.recovery_balance = Decimal("1.0")
        low_balance_user.profile.save()

        StaffRequest.objects.create(
            employee=low_balance_user.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_SUBMITTED,
            total_days=Decimal("1.0"),
            reason="Conge court",
        )

        response = self.client.get(reverse("administration:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["low_leave_count"], 1)
        self.assertEqual(response.context["low_recovery_count"], 1)
        self.assertEqual(response.context["pending_count"], 1)
        self.assertIn("1.5 jour(s)", json.loads(response.context["leave_chart_labels"]))
        self.assertIn("1 unite(s)", json.loads(response.context["recovery_chart_labels"]))

    def test_admin_transmits_leave_request_to_direction(self):
        staff_request = StaffRequest.objects.create(
            employee=self.employee.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_ADMINISTRATION,
            total_days=Decimal("2.0"),
            reason="Conge familial",
        )

        response = self.client.post(
            reverse("administration:request_action", args=[staff_request.id, "approve"]),
            {"admin_comment": "Validation admin accordee."},
            follow=True,
        )

        staff_request.refresh_from_db()
        self.employee.profile.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(staff_request.status, StaffRequest.STATUS_SUBMITTED)
        self.assertEqual(staff_request.approval_stage, StaffRequest.APPROVAL_DIRECTION)
        self.assertEqual(self.employee.profile.leave_balance, Decimal("10.0"))
        self.assertTrue(
            RequestActionHistory.objects.filter(
                request=staff_request,
                action=RequestActionHistory.ACTION_APPROVED,
                actor=self.admin,
            ).exists()
        )

    def test_admin_transmits_absence_request_to_direction(self):
        staff_request = StaffRequest.objects.create(
            employee=self.employee.profile,
            request_type=StaffRequest.TYPE_ABSENCE,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_ADMINISTRATION,
            total_days=Decimal("2.0"),
            reason="Absence terrain",
        )

        response = self.client.post(
            reverse("administration:request_action", args=[staff_request.id, "approve"]),
            {"admin_comment": "Absence transmise a la direction."},
            follow=True,
        )

        staff_request.refresh_from_db()
        self.employee.profile.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(staff_request.status, StaffRequest.STATUS_SUBMITTED)
        self.assertEqual(staff_request.approval_stage, StaffRequest.APPROVAL_DIRECTION)
        self.assertEqual(self.employee.profile.recovery_balance, Decimal("6.0"))

    def test_admin_transmits_recovery_request_to_direction(self):
        staff_request = StaffRequest.objects.create(
            employee=self.employee.profile,
            request_type=StaffRequest.TYPE_RECOVERY,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_ADMINISTRATION,
            total_days=Decimal("3.0"),
            project_name="Mission",
        )

        response = self.client.post(
            reverse("administration:request_action", args=[staff_request.id, "approve"]),
            {"admin_comment": "Recuperation transmise a la direction."},
            follow=True,
        )

        staff_request.refresh_from_db()
        self.employee.profile.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(staff_request.status, StaffRequest.STATUS_SUBMITTED)
        self.assertEqual(staff_request.approval_stage, StaffRequest.APPROVAL_DIRECTION)
        self.assertEqual(self.employee.profile.recovery_balance, Decimal("6.0"))

    def test_admin_can_create_account_with_contract_type(self):
        response = self.client.post(
            reverse("administration:settings"),
            {
                "panel": "create",
                "create-account": "1",
                "username": "nouvel-agent",
                "password": "TestPass123!",
                "first_name": "Jean",
                "last_name": "Rakoto",
                "email": "jean@example.com",
                "employee_number": "EMP-010",
                "position": "Technicien",
                "contract_type": EmployeeProfile.CONTRACT_TYPE_CDI,
                "leave_balance": "15.0",
                "recovery_balance": "2.0",
                "role": EmployeeProfile.ROLE_USER,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        created_user = User.objects.get(username="nouvel-agent")
        self.assertEqual(created_user.profile.contract_type, EmployeeProfile.CONTRACT_TYPE_CDI)

    def test_admin_can_update_existing_account_and_log_history(self):
        response = self.client.post(
            reverse("administration:settings"),
            {
                "panel": "accounts",
                "profile_id": self.employee.profile.id,
                "update-account": "1",
                "username": "agent",
                "password": "",
                "first_name": "Mamy",
                "last_name": "Agent Modifie",
                "email": "agent@example.com",
                "employee_number": "EMP-004",
                "position": "Responsable terrain",
                "contract_end_date": "",
                "leave_balance": "12.0",
                "recovery_balance": "5.0",
                "role": EmployeeProfile.ROLE_USER,
            },
            follow=True,
        )

        self.employee.refresh_from_db()
        self.employee.profile.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.employee.last_name, "Agent Modifie")
        self.assertEqual(self.employee.profile.position, "Responsable terrain")
        self.assertTrue(
            AccountActionHistory.objects.filter(
                target_username="agent",
                action=AccountActionHistory.ACTION_UPDATED,
                actor=self.admin,
            ).exists()
        )

    def test_admin_can_delete_account_and_log_history(self):
        response = self.client.post(
            reverse("administration:settings"),
            {
                "panel": "accounts",
                "show_history": "1",
                "profile_id": self.employee_to_delete.profile.id,
                "delete-account": "1",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="agent_delete").exists())
        self.assertTrue(
            AccountActionHistory.objects.filter(
                target_username="agent_delete",
                action=AccountActionHistory.ACTION_DELETED,
                actor=self.admin,
            ).exists()
        )
