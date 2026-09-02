from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.administration.models import LoginBranding
from apps.personnel.models import Department, EmployeeProfile, Role, AnnualLeave, AnnualRecovery
from apps.personnel.leave_service import ensure_leave_window
from apps.personnel.recovery_service import ensure_recovery_window
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
                "start_date": "2026-07-13",
                "end_date": "2026-07-15",
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

    def test_leave_request_excludes_weekends_by_default_for_multi_day_period(self):
        response = self.client.post(
            reverse("requests_management:leave_create"),
            {
                "start_date": "2026-07-06",
                "end_date": "2026-07-17",
                "total_days": "",
                "remaining_days_for_reason": "",
                "reason": "Conge avec weekend",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        request_item = StaffRequest.objects.latest("id")
        self.assertEqual(request_item.total_days, Decimal("10"))
        self.assertEqual(request_item.remaining_days_for_reason, Decimal("0.0"))

    def test_leave_request_can_count_weekends_when_toggle_is_disabled(self):
        self.user.profile.leave_balance = Decimal("20.0")
        self.user.profile.save()

        response = self.client.post(
            reverse("requests_management:leave_create"),
            {
                "start_date": "2026-07-06",
                "end_date": "2026-07-17",
                "exclude_weekends": "0",
                "total_days": "",
                "remaining_days_for_reason": "",
                "reason": "Conge avec weekend compte",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        request_item = StaffRequest.objects.latest("id")
        self.assertEqual(request_item.total_days, Decimal("12"))
        self.assertEqual(request_item.remaining_days_for_reason, Decimal("8.0"))

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

    def test_single_day_absence_with_hours_computes_fractional_total_days(self):
        response = self.client.post(
            reverse("requests_management:absence_create"),
            {
                "start_date": "2026-07-15",
                "end_date": "2026-07-15",
                "duration_mode": "custom_hours",
                "start_time": "08:00",
                "end_time": "11:00",
                "total_days": "",
                "remaining_days_for_reason": "",
                "reason": "Rendez-vous medical",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        request_item = StaffRequest.objects.latest("id")
        self.assertEqual(request_item.total_days, Decimal("0.4"))
        self.assertEqual(request_item.remaining_days_for_reason, Decimal("3.6"))
        self.assertEqual(request_item.period_label, "15/07/2026 08:00 - 11:00")

    def test_single_day_absence_on_weekend_is_rejected_when_weekend_exclusion_is_active(self):
        response = self.client.post(
            reverse("requests_management:absence_create"),
            {
                "start_date": "2026-07-11",
                "end_date": "2026-07-11",
                "duration_mode": "full_day",
                "total_days": "",
                "remaining_days_for_reason": "",
                "reason": "Absence samedi",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(StaffRequest.objects.filter(reason="Absence samedi").count(), 0)
        self.assertContains(response, "La periode selectionnee ne contient aucun jour ouvrable.")

    def test_single_day_leave_full_day_mode_forces_one_day_and_clears_hours(self):
        response = self.client.post(
            reverse("requests_management:leave_create"),
            {
                "start_date": "2026-07-20",
                "end_date": "2026-07-20",
                "duration_mode": "full_day",
                "start_time": "08:00",
                "end_time": "10:00",
                "total_days": "0.3",
                "remaining_days_for_reason": "",
                "reason": "Conge personnel",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        request_item = StaffRequest.objects.latest("id")
        self.assertEqual(request_item.total_days, Decimal("1.0"))
        self.assertEqual(request_item.remaining_days_for_reason, Decimal("9.0"))
        self.assertIsNone(request_item.start_time)
        self.assertIsNone(request_item.end_time)

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
        self.user.profile.save()
        ensure_leave_window(self.user.profile)
        AnnualLeave.objects.filter(employee=self.user.profile).update(consumed=Decimal("2.0"))

        response = self.client.post(
            reverse("requests_management:delete", args=[request_item.id]),
            follow=True,
        )

        self.user.profile.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(StaffRequest.objects.filter(id=request_item.id).exists())
        from apps.personnel.leave_service import get_leave_balance
        self.assertEqual(get_leave_balance(self.user.profile), Decimal("56.0"))

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
        ensure_recovery_window(self.user.profile)
        AnnualRecovery.objects.filter(employee=self.user.profile).update(balance=Decimal("4.0"))
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

        request_item.refresh_from_db()
        self.user.profile.refresh_from_db()
        from apps.personnel.recovery_service import get_recovery_balance
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request_item.status, StaffRequest.STATUS_APPROVED)
        self.assertEqual(request_item.approval_stage, StaffRequest.APPROVAL_COMPLETED)
        self.assertEqual(get_recovery_balance(self.user.profile), Decimal("14.0"))

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

    def test_employee_dashboard_displays_cancelled_request_count(self):
        StaffRequest.objects.create(
            employee=self.user.profile,
            request_type=StaffRequest.TYPE_LEAVE,
            status=StaffRequest.STATUS_CANCELLED,
            approval_stage=StaffRequest.APPROVAL_COMPLETED,
            total_days=1,
            remaining_days_for_reason=9,
            reason="Conge annule",
        )

        response = self.client.get(reverse("personnel:dashboard"))
        refresh_response = self.client.get(reverse("personnel:dashboard_data"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Annulees")
        self.assertContains(response, 'id="employee-cancelled-count">1</strong>', html=False)
        self.assertEqual(refresh_response.status_code, 200)
        self.assertEqual(refresh_response.json()["cancelled_count"], 1)

    def test_full_direction_approval_flow_creates_notification_and_updates_status(self):
        request_item = StaffRequest.objects.create(
            employee=self.user.profile,
            request_type=StaffRequest.TYPE_ABSENCE,
            status=StaffRequest.STATUS_SUBMITTED,
            approval_stage=StaffRequest.APPROVAL_DIRECTION,
            total_days=Decimal("1.0"),
            reason="Absence test direction",
            hierarchical_signature="chef",
            administration_signature="admin",
        )
        ensure_recovery_window(self.user.profile)
        AnnualRecovery.objects.filter(employee=self.user.profile).update(balance=Decimal("4.0"))

        direction_user = User.objects.create_user(username="direction", password="TestPass123!")
        direction_profile = direction_user.profile
        direction_profile.role = self.direction_role
        direction_profile.save()

        self.client.logout()
        self.client.login(username="direction", password="TestPass123!")

        response = self.client.post(
            reverse("administration:request_action", args=[request_item.id, "approve"]),
            {"admin_comment": "Accepte par la direction."},
            follow=True,
        )

        request_item.refresh_from_db()
        self.user.profile.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request_item.status, StaffRequest.STATUS_APPROVED)
        self.assertEqual(request_item.approval_stage, StaffRequest.APPROVAL_COMPLETED)
        self.assertEqual(request_item.direction_signature, "direction")

        from apps.administration.models import Notification
        notification = Notification.objects.filter(
            recipient=self.user,
            notification_type=Notification.TYPE_REQUEST_APPROVED,
            request=request_item,
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn("accept", notification.title.lower())

        self.client.logout()
        self.client.login(username="agent", password="TestPass123!")
        dashboard_response = self.client.get(reverse("personnel:dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "Approuvee")
        self.assertContains(dashboard_response, str(request_item.id))

    def test_employee_can_access_notifications_page(self):
        from apps.administration.models import Notification

        Notification.objects.create(
            recipient=self.user,
            notification_type=Notification.TYPE_REQUEST_APPROVED,
            title="Demande approuvee",
            message="Votre demande a ete approuvee.",
            request=StaffRequest.objects.create(
                employee=self.user.profile,
                request_type=StaffRequest.TYPE_LEAVE,
                status=StaffRequest.STATUS_APPROVED,
                approval_stage=StaffRequest.APPROVAL_COMPLETED,
                total_days=1,
                remaining_days_for_reason=9,
                reason="Conge teste",
            ),
        )

        response = self.client.get(reverse("administration:notifications"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Demande approuvee")
        self.assertContains(response, "Votre demande a ete approuvee.")


class RecoveryLimitTests(TestCase):
    """Tests de la limite annuelle configurable de recuperation par employe."""

    def setUp(self):
        self.employee_role = Role.objects.create(
            code=EmployeeProfile.ROLE_USER,
            label_fr="Employe",
            portal=Role.PORTAL_EMPLOYEE,
        )
        self.admin_role = Role.objects.create(
            code=EmployeeProfile.ROLE_ADMIN,
            label_fr="Administrateur",
            portal=Role.PORTAL_ADMIN,
            can_manage_settings=True,
        )
        self.user = User.objects.create_user(
            username="recov_agent",
            password="TestPass123!",
            first_name="Soa",
            last_name="Agent",
        )
        self.user.profile.role = self.employee_role
        self.user.profile.save()
        self.client.login(username="recov_agent", password="TestPass123!")
        self._set_branding(Decimal("15"), enabled=True)

    # --- Helpers ---
    def _set_branding(self, limit=Decimal("15"), enabled=True):
        branding = LoginBranding.objects.first()
        if not branding:
            branding = LoginBranding.objects.create()
        branding.recovery_limit_enabled = enabled
        branding.recovery_annual_limit = limit
        branding.save()

    def _set_balance(self, amount, year=2026):
        ensure_recovery_window(self.user.profile)
        ar, _ = AnnualRecovery.objects.get_or_create(
            employee=self.user.profile,
            year=year,
            defaults={"balance": Decimal("0"), "consumed": Decimal("0")},
        )
        ar.balance = amount
        ar.save(update_fields=["balance"])

    def _recovery_post(self, line_count, year=2026, start_day=2):
        data = {
            "project_name": "",
            "reason": "test recuperation",
            "recovery_lines-TOTAL_FORMS": str(line_count),
            "recovery_lines-INITIAL_FORMS": "0",
            "recovery_lines-MIN_NUM_FORMS": "0",
            "recovery_lines-MAX_NUM_FORMS": "1000",
        }
        for i in range(line_count):
            day = start_day + i
            data[f"recovery_lines-{i}-work_date"] = f"{year}-03-{day:02d}"
            data[f"recovery_lines-{i}-work_description"] = "travaux"
            data[f"recovery_lines-{i}-start_time"] = "08:00"
            data[f"recovery_lines-{i}-end_time"] = "17:00"
            data[f"recovery_lines-{i}-is_holiday"] = "false"
        return data

    def _count_recovery_requests(self):
        return StaffRequest.objects.filter(
            employee=self.user.profile, request_type=StaffRequest.TYPE_RECOVERY
        ).count()

    @staticmethod
    def _url():
        return reverse("requests_management:recovery_create")

    # --- Service (calcul) ---
    def test_service_per_year_and_boundary(self):
        from apps.personnel.recovery_service import check_recovery_request_limit

        # Sous la limite : autorise
        ok, limit = check_recovery_request_limit(self.user.profile, {2026: Decimal("14")})
        self.assertTrue(ok)
        self.assertEqual(limit, Decimal("15"))
        # Atteindre exactement la limite via une soumission : autorise (CAP inclusif)
        ok2, _ = check_recovery_request_limit(self.user.profile, {2026: Decimal("15")})
        self.assertTrue(ok2)
        # Depasser la limite : bloque
        ok3, _ = check_recovery_request_limit(self.user.profile, {2026: Decimal("15.1")})
        self.assertFalse(ok3)
        # Solde deja a la limite : toute nouvelle soumission bloquee
        self._set_balance(Decimal("15"), year=2026)
        ok4, _ = check_recovery_request_limit(self.user.profile, {2026: Decimal("0.1")})
        self.assertFalse(ok4)
        # Respect de l'annee : 2026 plein, 2027 libre
        ok5, _ = check_recovery_request_limit(
            self.user.profile, {2026: Decimal("1"), 2027: Decimal("10")}
        )
        self.assertFalse(ok5)

    def test_service_disabled_allows_any(self):
        from apps.personnel.recovery_service import check_recovery_request_limit

        self._set_branding(Decimal("15"), enabled=False)
        self._set_balance(Decimal("15"), year=2026)
        ok, limit = check_recovery_request_limit(self.user.profile, {2026: Decimal("100")})
        self.assertTrue(ok)
        self.assertEqual(limit, Decimal("15"))

    # --- Backend (soumission) ---
    def test_balance_below_limit_allowed(self):
        self._set_balance(Decimal("0"))
        before = self._count_recovery_requests()
        response = self.client.post(self._url(), self._recovery_post(5))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._count_recovery_requests(), before + 1)

    def test_balance_at_limit_blocked(self):
        self._set_balance(Decimal("15"))
        before = self._count_recovery_requests()
        response = self.client.post(self._url(), self._recovery_post(1))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._count_recovery_requests(), before)
        self.assertContains(response, "limite maximale de recuperation")

    def test_exceeding_limit_blocked(self):
        self._set_balance(Decimal("0"))
        before = self._count_recovery_requests()
        response = self.client.post(self._url(), self._recovery_post(20))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._count_recovery_requests(), before)
        self.assertContains(response, "limite maximale de recuperation")

    def test_limit_disabled_allows_any(self):
        self._set_branding(Decimal("15"), enabled=False)
        self._set_balance(Decimal("15"))
        before = self._count_recovery_requests()
        response = self.client.post(self._url(), self._recovery_post(10))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._count_recovery_requests(), before + 1)

    def test_limit_changed_to_other_value(self):
        self._set_branding(Decimal("20"), enabled=True)
        # 15 sur 20 : autorise
        self._set_balance(Decimal("15"))
        before = self._count_recovery_requests()
        resp_ok = self.client.post(self._url(), self._recovery_post(5))
        self.assertEqual(resp_ok.status_code, 302)
        self.assertEqual(self._count_recovery_requests(), before + 1)
        # 20 atteint : bloque
        self._set_balance(Decimal("20"))
        resp_block = self.client.post(self._url(), self._recovery_post(1))
        self.assertEqual(resp_block.status_code, 200)
        self.assertEqual(self._count_recovery_requests(), before + 1)

    def test_per_year_isolation_2026_vs_2027(self):
        self._set_balance(Decimal("15"), year=2026)
        self._set_balance(Decimal("0"), year=2027)
        # 2027 encore libre : autorise
        before = self._count_recovery_requests()
        resp_2027 = self.client.post(self._url(), self._recovery_post(3, year=2027))
        self.assertEqual(resp_2027.status_code, 302)
        self.assertEqual(self._count_recovery_requests(), before + 1)
        # 2026 deja plein : bloque
        resp_2026 = self.client.post(self._url(), self._recovery_post(1, year=2026))
        self.assertEqual(resp_2026.status_code, 200)
        self.assertEqual(self._count_recovery_requests(), before + 1)

    def test_existing_recoveries_not_modified(self):
        self._set_balance(Decimal("15"))
        self.client.post(self._url(), self._recovery_post(1))
        # Le solde existe toujours et n'a pas ete supprime/reduit par le blocage
        ar = AnnualRecovery.objects.get(employee=self.user.profile, year=2026)
        self.assertEqual(ar.balance, Decimal("15"))
        self.assertTrue(AnnualRecovery.objects.filter(employee=self.user.profile).exists())

    # --- Audit (parametres RH) ---
    def test_hr_params_limit_change_audited(self):
        from apps.administration.models import AccountActionHistory

        admin_user = User.objects.create_user(
            username="recov_rh", password="TestPass123!"
        )
        admin_user.profile.role = self.admin_role
        admin_user.profile.save()
        self.client.login(username="recov_rh", password="TestPass123!")

        branding = LoginBranding.objects.first()
        if not branding:
            branding = LoginBranding.objects.create()
        branding.recovery_limit_enabled = True
        branding.recovery_annual_limit = Decimal("15")
        branding.save()

        before = AccountActionHistory.objects.count()
        response = self.client.post(
            reverse("administration:settings") + "?panel=human_resources",
            {
                "save-hr-params": "1",
                "panel": "human_resources",
                "annual_leave_quota": "30",
                "leave_window_size": "3",
                "absence_limit_enabled": "on",
                "absence_annual_limit": "15",
                "recovery_limit_enabled": "on",
                "recovery_annual_limit": "20",
                "contact_enabled": "on",
                "whatsapp_enabled": "on",
                "whatsapp_number": "+261347794791",
                "email_contact_enabled": "on",
                "email_contact": "support@example.com",
                "telegram_enabled": "on",
                "telegram_id": "@centrevalbio",
                "twitter_enabled": "on",
                "twitter_url": "https://x.com/centrevalbio",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AccountActionHistory.objects.count(), before + 1)
        entry = AccountActionHistory.objects.latest("created_at")
        self.assertIn("20", entry.details)
        self.assertIn("15", entry.details)
