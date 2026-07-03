from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from apps.administration.models import LoginBranding
from apps.personnel.models import EmployeeProfile
from apps.requests_management.models import RecoveryLine, StaffRequest


class Command(BaseCommand):
    help = "Charge des donnees de demonstration pour l'application Centre ValBio."

    def handle(self, *args, **options):
        branding, _ = LoginBranding.objects.get_or_create(
            id=1,
            defaults={
                "site_name": "Centre ValBio",
                "subtitle": "Centre International pour la Valorisation de la Biodiversite",
                "address": "BP 33 Ranomafana Ifanadiana 312",
                "email": "centrevalbio@gmail.com",
                "website": "www.centrevalbio.org",
                "announcement": "Bienvenue dans la gestion du personnel du centre ValBio.",
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Branding pret: {branding.site_name}"))

        demo_users = [
            {
                "username": "admin",
                "password": "Admin12345!",
                "first_name": "Mireille",
                "last_name": "Admin",
                "role": EmployeeProfile.ROLE_ADMIN,
                "position": "Responsable RH",
                "employee_number": "ADM-001",
                "leave_balance": Decimal("0"),
                "recovery_balance": Decimal("0"),
            },
            {
                "username": "cvbadmin",
                "password": "CvbAdmin12345!",
                "first_name": "CVB",
                "last_name": "Admin",
                "role": EmployeeProfile.ROLE_ADMIN,
                "position": "Administrateur principal",
                "employee_number": "CVB-ADMIN",
                "leave_balance": Decimal("0"),
                "recovery_balance": Decimal("0"),
            },
            {
                "username": "employe",
                "password": "Employe12345!",
                "first_name": "Aina",
                "last_name": "Rakoto",
                "role": EmployeeProfile.ROLE_USER,
                "position": "Technicien biodiversite",
                "employee_number": "EMP-001",
                "leave_balance": Decimal("18"),
                "recovery_balance": Decimal("6"),
            },
        ]

        for item in demo_users:
            user, created = User.objects.get_or_create(username=item["username"])
            if created:
                user.first_name = item["first_name"]
                user.last_name = item["last_name"]
                user.set_password(item["password"])
                user.is_staff = item["role"] == EmployeeProfile.ROLE_ADMIN
                user.is_superuser = False
                user.save()
            profile = user.profile
            profile.role = item["role"]
            profile.position = item["position"]
            profile.employee_number = item["employee_number"]
            profile.contract_end_date = date.today() + timedelta(days=365)
            profile.leave_balance = item["leave_balance"]
            profile.recovery_balance = item["recovery_balance"]
            profile.save()
            self.stdout.write(self.style.SUCCESS(f"Compte pret: {user.username}"))

        employee = User.objects.get(username="employe").profile
        leave_request, _ = StaffRequest.objects.get_or_create(
            employee=employee,
            request_type=StaffRequest.TYPE_LEAVE,
            start_date=date.today() + timedelta(days=10),
            defaults={
                "status": StaffRequest.STATUS_APPROVED,
                "end_date": date.today() + timedelta(days=14),
                "total_days": Decimal("5"),
                "reason": "Conge annuel",
            },
        )
        absence_request, _ = StaffRequest.objects.get_or_create(
            employee=employee,
            request_type=StaffRequest.TYPE_ABSENCE,
            start_date=date.today() + timedelta(days=2),
            defaults={
                "status": StaffRequest.STATUS_SUBMITTED,
                "end_date": date.today() + timedelta(days=3),
                "total_days": Decimal("2"),
                "remaining_days_for_reason": Decimal("8"),
                "reason": "Autorisation d'absence pour deplacement familial",
            },
        )
        recovery_request, _ = StaffRequest.objects.get_or_create(
            employee=employee,
            request_type=StaffRequest.TYPE_RECOVERY,
            project_name="Inventaire flore",
            defaults={
                "status": StaffRequest.STATUS_APPROVED,
                "reason": "Heures supplementaires sur terrain",
                "total_days": Decimal("6"),
            },
        )
        RecoveryLine.objects.get_or_create(
            request=recovery_request,
            work_date=date.today() - timedelta(days=4),
            work_description="Collecte de donnees en station",
            defaults={
                "start_time": "18:00",
                "end_time": "21:00",
                "duration_hours": Decimal("3"),
                "is_holiday": False,
            },
        )
        RecoveryLine.objects.get_or_create(
            request=recovery_request,
            work_date=date.today() - timedelta(days=3),
            work_description="Saisie et verification des observations",
            defaults={
                "start_time": "19:00",
                "end_time": "22:00",
                "duration_hours": Decimal("3"),
                "is_holiday": False,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demandes de demonstration pretes: {leave_request.id}, {absence_request.id}, {recovery_request.id}"
            )
        )
