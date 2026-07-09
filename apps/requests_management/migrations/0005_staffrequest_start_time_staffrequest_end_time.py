from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("requests_management", "0004_alter_staffrequest_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffrequest",
            name="end_time",
            field=models.TimeField(
                blank=True,
                null=True,
                verbose_name="Heure fin",
            ),
        ),
        migrations.AddField(
            model_name="staffrequest",
            name="start_time",
            field=models.TimeField(
                blank=True,
                null=True,
                verbose_name="Heure debut",
            ),
        ),
    ]
