from decimal import Decimal

from django.db import migrations


def migrate_recovery_balances(apps, schema_editor):
    """Migre les anciens soldes recovery_balance vers AnnualRecovery."""
    EmployeeProfile = apps.get_model("personnel", "EmployeeProfile")
    AnnualRecovery = apps.get_model("personnel", "AnnualRecovery")

    for profile in EmployeeProfile.objects.all():
        old_balance = profile.recovery_balance or Decimal("0")
        if old_balance <= 0:
            continue

        # Distribue l'ancien solde sur l'année courante (la plus récente de la fenêtre)
        current_year = 2026  # Année courante du serveur
        AnnualRecovery.objects.get_or_create(
            employee=profile,
            year=current_year,
            defaults={"balance": old_balance, "consumed": Decimal("0")},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("personnel", "0005_annualrecovery"),
    ]

    operations = [
        migrations.RunPython(migrate_recovery_balances, migrations.RunPython.noop),
    ]