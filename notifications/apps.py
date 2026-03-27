from django.apps import AppConfig
import os
class NotificationsConfig(AppConfig):
    default_auto_field = (
        "django_mongodb_backend.fields.ObjectIdAutoField"
        if os.getenv("DB_ENGINE") == "django_mongodb_backend"
        else "django.db.models.BigAutoField"
    )
    name = "notifications"
    verbose_name = "Notifications"
