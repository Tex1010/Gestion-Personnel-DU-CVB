from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("requests_management", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="recoveryline",
            name="is_holiday",
            field=models.BooleanField(default=False, verbose_name="Ferie"),
        ),
        migrations.RemoveField(
            model_name="recoveryline",
            name="initials",
        ),
    ]
