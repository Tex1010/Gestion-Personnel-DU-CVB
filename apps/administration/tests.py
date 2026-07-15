import json
from io import BytesIO
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from apps.accounts.utils import get_role_by_code
from apps.administration.models import AccountActionHistory, LoginBranding, RequestActionHistory
from apps.personnel.models import Department, EmployeeProfile
from apps.requests_management.models import StaffRequest


class AdministrationViewsTests(TestCase):
    def setUp(self):
        admin_role = get_role_by_code(EmployeeProfile.ROLE_ADMIN)
        direction_role = get_role_by_code(EmployeeProfile.ROLE_DIRECTION)
        user_role = get_role_by_code(EmployeeProfile.ROLE_USER)

        self.admin = User.objects.create_user(username="admin", password="TestPass123!")
        self.admin.is_staff = True
        self.admin.save()
        self.admin.profile.role = admin_role
        self.admin.profile.recovery_balance = Decimal("5.0")
        self.admin.profile.save()
        self.client.login(username="admin", password="TestPass123!")

        self.employee = User.objects.create_user(
            username="agent",
            password="TestPass123!",
            first_name="Mamy",
            last_name="Agent",
        )
        self.employee.profile.role = user_role
        self.employee.profile.position = "Technicien"
        self.employee.profile.leave_balance = Decimal("10.0")
        self.employee.profile.recovery_balance = Decimal("6.0")
        self.employee.profile.save()

        self.employee_to_delete = User.objects.create_user(
            username="agent_delete",
            password="TestPass123!",
        )
        self.employee_to_delete.profile.role = user_role
        self.employee_to_delete.profile.leave_balance = Decimal("4.0")
        self.employee_to_delete.profile.recovery_balance = Decimal("4.0")
        self.employee_to_delete.profile.save()

        self.direction = User.objects.create_user(
            username="direction",
            password="TestPass123!",
        )
        self.direction.profile.role = direction_role
        self.direction.profile.save()

    def _read_workbook_rows(self, response):
        workbook = load_workbook(filename=BytesIO(response.content))
        return list(workbook.active.iter_rows(values_only=True))

    def test_admin_dashboard_requires_admin_role(self):
        user_role = get_role_by_code(EmployeeProfile.ROLE_USER)
        user = User.objects.create_user(username="simple", password="TestPass123!")
        user.profile.role = user_role
        user.profile.save()
        self.client.login(username="simple", password="TestPass123!")

        response = self.client.get(reverse("administration:dashboard"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "acces a cette page")

    def test_admin_dashboard_exposes_low_balance_metrics_and_distributions(self):
        user_role = get_role_by_code(EmployeeProfile.ROLE_USER)
        low_balance_user = User.objects.create_user(
            username="agent_low",
            password="TestPass123!",
            first_name="Bodo",
            last_name="Petit",
        )
        low_balance_user.profile.role = user_role
        low_balance_user.profile.leave_balance = Decimal("1.5")
        low_balance_user.profile.recovery_balance = Decimal("1.0")
        low_balance_user.profile.save()

        StaffRequest.objects.create(
            employee=low_balance_user.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_ADMINISTRATION,
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

    def test_admin_dashboard_hides_cvbadmin_from_stats_and_tables(self):
        admin_role = get_role_by_code(EmployeeProfile.ROLE_ADMIN)
        hidden_admin = User.objects.create_user(
            username="cvbadmin",
            password="TestPass123!",
            first_name="Compte",
            last_name="Cache",
        )
        hidden_admin.profile.role = admin_role
        hidden_admin.profile.leave_balance = Decimal("0.0")
        hidden_admin.profile.recovery_balance = Decimal("0.0")
        hidden_admin.profile.save()

        response = self.client.get(reverse("administration:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["employee_count"], 3)
        self.assertNotContains(response, "Compte Cache")

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

    def test_admin_can_cancel_approved_request_and_restore_balance(self):
        staff_request = StaffRequest.objects.create(
            employee=self.employee.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_APPROVED,
            approval_stage=StaffRequest.APPROVAL_COMPLETED,
            total_days=Decimal("2.0"),
            reason="Conge annuel",
            admin_comment="Deja approuvee.",
        )
        self.employee.profile.leave_balance = Decimal("8.0")
        self.employee.profile.save(update_fields=["leave_balance", "updated_at"])

        response = self.client.post(
            reverse("administration:request_action", args=[staff_request.id, "cancel"]),
            follow=True,
        )

        staff_request.refresh_from_db()
        self.employee.profile.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(staff_request.status, StaffRequest.STATUS_CANCELLED)
        self.assertEqual(self.employee.profile.leave_balance, Decimal("10.0"))

    def test_requests_history_shows_cancel_action_for_admin_in_page_and_ajax_rows(self):
        staff_request = StaffRequest.objects.create(
            employee=self.employee.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_APPROVED,
            approval_stage=StaffRequest.APPROVAL_COMPLETED,
            total_days=Decimal("2.0"),
            reason="Conge annuel",
        )
        RequestActionHistory.objects.create(
            request=staff_request,
            actor=self.admin,
            action=RequestActionHistory.ACTION_APPROVED,
            previous_status=StaffRequest.STATUS_SUBMITTED,
            new_status=StaffRequest.STATUS_APPROVED,
            comment="Validation finale.",
        )

        overview_response = self.client.get(
            f"{reverse('administration:requests')}?show_history=1"
        )
        ajax_response = self.client.get(
            f"{reverse('administration:requests_overview_data')}?show_history=1",
            HTTP_X_REQUESTED_WITH="fetch",
        )

        cancel_url = reverse("administration:request_action", args=[staff_request.id, "cancel"])

        self.assertEqual(overview_response.status_code, 200)
        self.assertContains(overview_response, "Annuler")
        self.assertContains(overview_response, cancel_url)
        self.assertEqual(ajax_response.status_code, 200)
        self.assertIn(cancel_url, ajax_response.json()["requests_history_html"])

    def test_requests_history_hides_cancel_action_for_direction(self):
        staff_request = StaffRequest.objects.create(
            employee=self.employee.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_APPROVED,
            approval_stage=StaffRequest.APPROVAL_COMPLETED,
            total_days=Decimal("2.0"),
            reason="Conge annuel",
            direction_signature="direction",
        )
        RequestActionHistory.objects.create(
            request=staff_request,
            actor=self.admin,
            action=RequestActionHistory.ACTION_APPROVED,
            previous_status=StaffRequest.STATUS_SUBMITTED,
            new_status=StaffRequest.STATUS_APPROVED,
            comment="Validation finale.",
        )

        self.client.logout()
        self.client.login(username="direction", password="TestPass123!")

        overview_response = self.client.get(
            f"{reverse('administration:requests')}?show_history=1"
        )
        ajax_response = self.client.get(
            f"{reverse('administration:requests_overview_data')}?show_history=1",
            HTTP_X_REQUESTED_WITH="fetch",
        )

        cancel_url = reverse("administration:request_action", args=[staff_request.id, "cancel"])

        self.assertEqual(overview_response.status_code, 200)
        self.assertNotContains(overview_response, "<th>Annuler</th>", html=True)
        self.assertNotContains(overview_response, cancel_url)
        self.assertEqual(ajax_response.status_code, 200)
        self.assertNotIn(cancel_url, ajax_response.json()["requests_history_html"])

    def test_direction_cannot_cancel_approved_request(self):
        staff_request = StaffRequest.objects.create(
            employee=self.employee.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_APPROVED,
            approval_stage=StaffRequest.APPROVAL_COMPLETED,
            total_days=Decimal("2.0"),
            reason="Conge annuel",
        )
        starting_balance = self.employee.profile.leave_balance

        self.client.logout()
        self.client.login(username="direction", password="TestPass123!")

        response = self.client.post(
            reverse("administration:request_action", args=[staff_request.id, "cancel"]),
            follow=True,
        )

        staff_request.refresh_from_db()
        self.employee.profile.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(staff_request.status, StaffRequest.STATUS_APPROVED)
        self.assertEqual(self.employee.profile.leave_balance, starting_balance)
        self.assertContains(response, "seule la Ressource Humain (RH) peut annuler cette demande")

    def test_request_history_groups_multiple_actions_on_single_row(self):
        staff_request = StaffRequest.objects.create(
            employee=self.employee.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_DIRECTION,
            total_days=Decimal("2.0"),
            reason="Conge annuel",
            admin_comment="En attente de la direction.",
            hierarchical_signature="chef-service",
            administration_signature="admin",
        )
        RequestActionHistory.objects.create(
            request=staff_request,
            actor=self.admin,
            action=RequestActionHistory.ACTION_APPROVED,
            previous_status=StaffRequest.STATUS_SUBMITTED,
            new_status=StaffRequest.STATUS_SUBMITTED,
            comment="Validation admin.",
        )
        RequestActionHistory.objects.create(
            request=staff_request,
            actor=self.admin,
            action=RequestActionHistory.ACTION_APPROVED,
            previous_status=StaffRequest.STATUS_SUBMITTED,
            new_status=StaffRequest.STATUS_SUBMITTED,
            comment="Validation chef deja enregistree.",
        )

        response = self.client.get(
            f"{reverse('administration:requests')}?show_history=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["history_requests"]), 1)
        history_row = response.context["history_requests"][0]
        self.assertEqual(history_row["request"].id, staff_request.id)
        self.assertEqual(history_row["stage_statuses"][0]["status"], "Approuvee")
        self.assertEqual(history_row["stage_statuses"][1]["status"], "Approuvee")
        self.assertEqual(history_row["stage_statuses"][2]["status"], "Aucune action")

    def test_requests_overview_displays_total_days_in_pending_and_history_tables(self):
        pending_request = StaffRequest.objects.create(
            employee=self.employee.profile,
            request_type=StaffRequest.TYPE_ABSENCE,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_ADMINISTRATION,
            total_days=Decimal("4.0"),
            reason="Mission terrain",
            administration_signature="admin",
        )
        RequestActionHistory.objects.create(
            request=pending_request,
            actor=self.admin,
            action=RequestActionHistory.ACTION_APPROVED,
            previous_status=StaffRequest.STATUS_SUBMITTED,
            new_status=StaffRequest.STATUS_SUBMITTED,
            comment="Transmission en cours.",
        )

        response = self.client.get(
            f"{reverse('administration:requests')}?show_history=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nombre de jours")
        self.assertContains(response, "4,0")

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

    def test_export_requests_returns_excel_file_even_for_csv_route(self):
        StaffRequest.objects.create(
            employee=self.employee.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_ADMINISTRATION,
            total_days=Decimal("2.0"),
            reason="Conge test",
        )

        response = self.client.get(
            reverse("administration:export_requests", args=["csv"])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("demandes.xlsx", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"PK"))

    def test_export_table_accounts_returns_excel_file(self):
        response = self.client.get(
            reverse("administration:export_table", args=["accounts"])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("comptes-employes.xlsx", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"PK"))

    def test_export_table_accounts_applies_search_from_visible_table(self):
        user_role = get_role_by_code(EmployeeProfile.ROLE_USER)
        searched_user = User.objects.create_user(
            username="tendry",
            password="TestPass123!",
            first_name="Tendry",
            last_name="Rakoto",
        )
        searched_user.profile.role = user_role
        searched_user.profile.position = "Analyste"
        searched_user.profile.leave_balance = Decimal("8.0")
        searched_user.profile.recovery_balance = Decimal("2.0")
        searched_user.profile.save()

        response = self.client.get(
            reverse("administration:export_table", args=["accounts"]),
            {"search": "tendry"},
        )

        self.assertEqual(response.status_code, 200)
        rows = self._read_workbook_rows(response)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], searched_user.profile.display_name)
        self.assertEqual(rows[1][4], "Analyste")

    def test_export_table_departments_matches_displayed_active_rows(self):
        Department.objects.create(name="Administration", code="ADM", is_active=True)
        Department.objects.create(name="Archive", code="ARC", is_active=False)

        response = self.client.get(
            reverse("administration:export_table", args=["departments"])
        )

        self.assertEqual(response.status_code, 200)
        rows = self._read_workbook_rows(response)
        exported_names = [row[0] for row in rows[1:]]
        self.assertIn("Administration", exported_names)
        self.assertNotIn("Archive", exported_names)

    def test_export_table_requests_history_returns_excel_file(self):
        request_item = StaffRequest.objects.create(
            employee=self.employee.profile,
            request_type=StaffRequest.TYPE_ABSENCE,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_ADMINISTRATION,
            total_days=Decimal("1.0"),
            reason="Mission",
            hierarchical_signature="chef",
            administration_signature="admin",
        )
        RequestActionHistory.objects.create(
            request=request_item,
            actor=self.admin,
            action=RequestActionHistory.ACTION_APPROVED,
            previous_status=StaffRequest.STATUS_SUBMITTED,
            new_status=StaffRequest.STATUS_SUBMITTED,
            comment="Validation",
        )

        response = self.client.get(
            reverse("administration:export_table", args=["requests_history"])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("historique-demandes.xlsx", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"PK"))

    def test_branding_settings_displays_email_alert_toggle(self):
        response = self.client.get(
            f"{reverse('administration:settings')}?panel=branding"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alertes email a la soumission")
        self.assertContains(response, "request_submission_email_enabled")

    def test_request_notifications_state_returns_pending_request_summary(self):
        request_item = StaffRequest.objects.create(
            employee=self.employee.profile,
            request_type=StaffRequest.TYPE_ABSENCE,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_ADMINISTRATION,
            total_days=Decimal("1.0"),
            reason="Mission",
        )

        response = self.client.get(reverse("administration:request_notifications_state"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pending_count"], 1)
        self.assertIn(str(request_item.id), payload["latest_event_key"])
        self.assertEqual(payload["latest_request"]["employee_name"], "Mamy Agent")

    def test_request_email_alert_respects_admin_toggle(self):
        branding = LoginBranding.objects.create(
            site_name="Centre ValBio",
            subtitle="Gestion",
            email="admin@example.com",
            request_submission_email_enabled=False,
        )
        request_item = StaffRequest.objects.create(
            employee=self.employee.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_ADMINISTRATION,
            total_days=Decimal("1.0"),
            reason="Conge court",
        )

        with patch("apps.administration.views.send_mail") as mocked_send_mail:
            from apps.administration.views import _send_request_email_alert

            result = _send_request_email_alert(request_item, branding=branding)

        self.assertFalse(result)
        mocked_send_mail.assert_not_called()
