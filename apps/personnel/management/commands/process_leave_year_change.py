"""
Commande de gestion : process_leave_year_change

Applique la logique de gestion des congés par année (fenêtre glissante de 3 ans)
sur tous les employés.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.personnel.models import AnnualLeave, EmployeeProfile
from apps.personnel.leave_service import (
    ensure_leave_window,
    get_current_year,
    get_leave_window_years,
)


class Command(BaseCommand):
    help = "Applique la fenêtre glissante de congés (3 ans) sur tous les employés."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche ce qui serait fait sans modifier la base de données.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        current_year = get_current_year()
        window_years = get_leave_window_years(current_year)

        self.stdout.write(
            self.style.NOTICE(
                f"Année courante : {current_year} | Fenêtre : {window_years[0]} - {window_years[1]} - {window_years[2]}"
            )
        )

        employees = EmployeeProfile.objects.exclude(user__username="cvbadmin")
        total = employees.count()
        self.stdout.write(f"Employés à traiter : {total}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("Mode DRY-RUN : aucune modification ne sera effectuée.")
            )

        processed = 0
        with transaction.atomic():
            for emp in employees:
                if dry_run:
                    from apps.personnel.leave_service import get_annual_quota, get_leave_dashboard_data

                    quota = get_annual_quota()
                    window_data = get_leave_dashboard_data(emp)
                    old_leaves = AnnualLeave.objects.filter(
                        employee=emp, year__lt=window_years[0]
                    ).count()
                    self.stdout.write(
                        f"  {emp.display_name} : quota={quota}, "
                        f"anciennes années à supprimer={old_leaves}, "
                        f"fenêtre={[{d['year']: d['remaining']} for d in window_data]}"
                    )
                else:
                    ensure_leave_window(emp)
                processed += 1

            if not dry_run:
                AnnualLeave.objects.filter(year__lt=window_years[0]).delete()
                # Reinitialiser le solde d'événements familiaux (10 jours/an)
                from apps.hr_events.hr_events_service import reset_family_event_balances

                reset_family_event_balances()
                self.stdout.write(
                    self.style.NOTICE("Solde d'événements familiaux réinitialisé à 10 jours.")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Terminé. {processed}/{total} employés traités."
                + (" (mode dry-run)" if dry_run else "")
            )
        )
