from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.personnel.models import EmployeeProfile


class AccountsViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="employe_test",
            password="TestPass123!",
            first_name="Jean",
            last_name="Employe",
        )
        self.user.profile.role = EmployeeProfile.ROLE_USER
        self.user.profile.save()
        self.admin_user = User.objects.create_user(
            username="admin_test",
            password="TestPass123!",
            email="admin@example.com",
        )
        self.admin_user.is_staff = True
        self.admin_user.save()
        self.admin_user.profile.role = EmployeeProfile.ROLE_ADMIN
        self.admin_user.profile.save()

    def test_login_page_loads(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connexion")

    def test_login_rejects_wrong_selected_role(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "role": EmployeeProfile.ROLE_ADMIN,
                "username": "employe_test",
                "password": "TestPass123!",
            },
            follow=True,
        )
        self.assertContains(response, "Le role choisi ne correspond pas")

    def test_admin_can_login_as_admin(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "role": EmployeeProfile.ROLE_ADMIN,
                "username": "admin_test",
                "password": "TestPass123!",
            },
            follow=True,
        )

        self.admin_user.refresh_from_db()
        self.admin_user.profile.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertEqual(self.admin_user.profile.role, EmployeeProfile.ROLE_ADMIN)

    def test_admin_can_login_as_employee(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "role": EmployeeProfile.ROLE_USER,
                "username": "admin_test",
                "password": "TestPass123!",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertContains(response, "Accueil employe")

    def test_password_change_redirects_to_admin_dashboard_when_logged_in_as_admin(self):
        self.client.login(username="admin_test", password="TestPass123!")
        session = self.client.session
        session["portal_role"] = EmployeeProfile.ROLE_ADMIN
        session.save()

        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": "TestPass123!",
                "new_password1": "AdminPass456!",
                "new_password2": "AdminPass456!",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tableau de bord admin")
