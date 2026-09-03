from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requests_management', '0008_staffrequest_recovery_consumption'),
    ]

    operations = [
        migrations.AddField(
            model_name='staffrequest',
            name='available_balance_at_request',
            field=models.DecimalField(
                default=0,
                decimal_places=1,
                help_text='Solde (conge ou recuperation) disponible au moment de la soumission.',
                max_digits=6,
                verbose_name='Solde disponible au moment de la demande',
            ),
        ),
        migrations.AddField(
            model_name='staffrequest',
            name='exceptional_days',
            field=models.DecimalField(
                default=0,
                decimal_places=1,
                help_text='Jours demandes au-dela du solde disponible. 0 si pas de depassement.',
                max_digits=6,
                verbose_name='Jours excedentaires (absence exceptionnelle)',
            ),
        ),
        migrations.AddField(
            model_name='staffrequest',
            name='exceptional_acknowledged',
            field=models.BooleanField(
                default=False,
                help_text="L'employe accepte que les jours excedentaires soient deduits de son salaire.",
                verbose_name='Acceptation retenue salariale',
            ),
        ),
        migrations.AddField(
            model_name='staffrequest',
            name='is_exceptional_absence',
            field=models.BooleanField(
                default=False,
                help_text='Vrai si la demande inclut un depassement du solde (absence exceptionnelle).',
                verbose_name='Absence exceptionnelle avec retenue salariale',
            ),
        ),
    ]