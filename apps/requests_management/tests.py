from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.administration.models import LoginBranding
from apps.personnel.models import Department, EmployeeProfile, Role
from apps.requests_management.models import StaffRequest


class RequestsTests(TestCase):
    def setUp(self):
        self.employee_role = Role.objects.create(
            code=EmployeeProfile.ROLE_USER,
            label_fr="Employe",
            portal=Role.PORTAL_EMPLOYEE,
        )
        self.hierarchical_role = Role.objects.create(
            code=EmployeeProfile.ROLE_HIERARCHICAL,
            label_fr="Chef hierarchique",
            portal=Role.PORTAL_ADMIN,
            can_validate_hierarchy=True,
        )
        self.direction_role = Role.objects.create(
            code=EmployeeProfile.ROLE_DIRECTION,
            label_fr="Direction",
            portal=Role.PORTAL_ADMIN,
            can_validate_direction=True,
        )
        self.user = User.objects.create_user(
            username="agent",
            password="TestPass123!",
            first_name="Mamy",
            last_name="Agent",
        )
        self.user.profile.role = self.employee_role
        self.user.profile.leave_balance = 10
        self.user.profile.recovery_balance = 4
        self.user.profile.save()
        self.client.login(username="agent", password="TestPass123!")

    def test_absence_request_creation(self):
        response = self.client.post(
            reverse("requests_management:absence_create"),
            {
                "start_date": "2026-07-01",
                "end_date": "2026-07-02",
                "total_days": "2",
                "remaining_days_for_reason": "5",
                "reason": "Presence obligatoire a l'administration communale",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StaffRequest.objects.count(), 1)
        request_item = StaffRequest.objects.first()
        self.assertEqual(request_item.request_type, StaffRequest.TYPE_ABSENCE)
        self.assertEqual(request_item.remaining_days_for_reason, 2)

    def test_leave_request_creation_uses_leave_type_and_remaining_balance(self):
        response = self.client.post(
            reverse("requests_management:leave_create"),
            {
                "start_date": "2026-07-10",
                "end_date": "2026-07-12",
                "total_days": "3",
                "remaining_days_for_reason": "",
                "reason": "Conge annuel",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        request_item = StaffRequest.objects.latest("id")
        self.assertEqual(request_item.request_type, StaffRequest.TYPE_LEAVE)
        self.assertEqual(request_item.remaining_days_for_reason, 7)

    def test_request_submission_sets_floating_notification(self):
        self.client.post(
            reverse("requests_management:absence_create"),
            {
                "start_date": "2026-07-15",
                "end_date": "2026-07-15",
                "total_days": "1",
                "remaining_days_for_reason": "4",
                "reason": "Demande urgente",
            },
        )

        session = self.client.session
        self.assertIn("floating_notification", session)
        self.assertEqual(session["floating_notification"]["title"], "Demande envoyee")

    def test_employee_can_delete_own_request_from_history(self):
        request_item = StaffRequest.objects.create(
            employee=self.user.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_SUBMITTED,
            total_days=2,
            remaining_days_for_reason=8,
            reason="Conge test",
        )

        response = self.client.post(
            reverse("requests_management:delete", args=[request_item.id]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(StaffRequest.objects.filter(id=request_item.id).exists())

    def test_employee_can_delete_already_processed_request(self):
        request_item = StaffRequest.objects.create(
            employee=self.user.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_APPROVED,
            approval_stage=StaffRequest.APPROVAL_COMPLETED,
            total_days=2,
            remaining_days_for_reason=8,
            reason="Conge approuve",
        )
        self.user.profile.leave_balance = 8
        self.user.profile.save()

        response = self.client.post(
            reverse("requests_management:delete", args=[request_item.id]),
            follow=True,
        )

        self.user.profile.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(StaffRequest.objects.filter(id=request_item.id).exists())
        self.assertEqual(self.user.profile.leave_balance, 10)

    def test_hierarchical_approval_advances_request_to_next_stage(self):
        department = Department.objects.create(name="Informatique")
        self.user.profile.department = department
        self.user.profile.save()
        approver = User.objects.create_user(username="chef", password="TestPass123!")
        approver_profile = approver.profile
        approver_profile.role = self.hierarchical_role
        approver_profile.department = department
        approver_profile.save()
        self.client.logout()
        self.client.login(username="chef", password="TestPass123!")

        request_item = StaffRequest.objects.create(
            employee=self.user.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_HIERARCHY,
            total_days=2,
            remaining_days_for_reason=8,
            reason="Conge test",
        )

        response = self.client.post(
            reverse("administration:request_action", args=[request_item.id, "approve"]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        request_item.refresh_from_db()
        self.assertEqual(request_item.approval_stage, StaffRequest.APPROVAL_ADMINISTRATION)
        self.assertEqual(request_item.status, StaffRequest.STATUS_SUBMITTED)

    def test_direction_approval_finalizes_request_and_updates_balance(self):
        request_item = StaffRequest.objects.create(
            employee=self.user.profile,
            request_type=StaffRequest.TYPE_RECOVERY,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_DIRECTION,
            total_days=2,
            remaining_days_for_reason=0,
            reason="Recuperation test",
        )
        direction_user = User.objects.create_user(username="direction", password="TestPass123!")
        direction_profile = direction_user.profile
        direction_profile.role = self.direction_role
        direction_profile.save()
        self.client.logout()
        self.client.login(username="direction", password="TestPass123!")

        response = self.client.post(
            reverse("administration:request_action", args=[request_item.id, "approve"]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        request_item.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(request_item.status, StaffRequest.STATUS_APPROVED)
        self.assertEqual(request_item.approval_stage, StaffRequest.APPROVAL_COMPLETED)
        self.assertEqual(self.user.profile.recovery_balance, 6)

    def test_employee_can_open_printable_request(self):
        request_item = StaffRequest.objects.create(
            employee=self.user.profile,
            request_type=StaffRequest.TYPE_ABSENCE,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_HIERARCHY,
            total_days=1,
            remaining_days_for_reason=3,
            reason="Absence ponctuelle",
        )

        response = self.client.get(reverse("requests_management:print", args=[request_item.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Suivi des validations")

    def test_employee_can_download_request_as_pdf(self):
        request_item = StaffRequest.objects.create(
            employee=self.user.profile,
            request_type=StaffRequest.TYPE_ABSENCE,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_HIERARCHY,
            total_days=1,
            remaining_days_for_reason=3,
            reason="Absence ponctuelle",
        )

        response = self.client.get(
            f"{reverse('requests_management:print', args=[request_item.id])}?download=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF-1.4"))

    def test_employee_dashboard_exposes_pdf_and_delete_actions_for_processed_request(self):
        request_item = StaffRequest.objects.create(
            employee=self.user.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_APPROVED,
            approval_stage=StaffRequest.APPROVAL_COMPLETED,
            total_days=2,
            remaining_days_for_reason=8,
            reason="Conge approuve",
        )

        response = self.client.get(reverse("personnel:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("requests_management:print", args=[request_item.id]))
        self.assertContains(
            response,
            f"{reverse('requests_management:print', args=[request_item.id])}?download=1",
        )
        self.assertContains(response, reverse("requests_management:delete", args=[request_item.id]))

    def test_employee_dashboard_email_action_uses_admin_branding_email(self):
        LoginBranding.objects.create(email="direction@example.com")
        request_item = StaffRequest.objects.create(
            employee=self.user.profile,
            request_type=StaffRequest.TYPE_ABSENCE,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_HIERARCHY,
            total_days=1,
            remaining_days_for_reason=3,
            reason="Absence test",
        )

        response = self.client.get(reverse("personnel:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-email="direction@example.com"')
        self.assertContains(response, reverse("requests_management:print", args=[request_item.id]))

    def test_employee_dashboard_refresh_email_action_uses_admin_branding_email(self):
        LoginBranding.objects.create(email="direction@example.com")
        StaffRequest.objects.create(
            employee=self.user.profile,
            request_type=StaffRequest.TYPE_RECOVERY,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_HIERARCHY,
            total_days=1,
            remaining_days_for_reason=3,
            reason="Recuperation test",
        )

        response = self.client.get(reverse("personnel:dashboard_data"))

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-email="direction@example.com"', response.json()["recovery_requests_html"])
