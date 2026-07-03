from django.apps import AppConfig


class PersonnelConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.personnel"

    def ready(self):
        import apps.personnel.signals  # noqa: F401
