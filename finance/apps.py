from django.apps import AppConfig
import os
class FinanceConfig(AppConfig):
    default_auto_field = (
        "django_mongodb_backend.fields.ObjectIdAutoField"
        if os.getenv("DB_ENGINE") == "django_mongodb_backend"
        else "django.db.models.BigAutoField"
    )
    name = 'finance'

    def ready(self):
        # Import signal handlers
        import finance.signals  # noqa: F401