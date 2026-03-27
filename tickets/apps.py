"""Tickets app configuration."""

from django.apps import AppConfig
import os
class TicketsConfig(AppConfig):
    """Configuration for the Tickets app."""
    
    default_auto_field = (
        "django_mongodb_backend.fields.ObjectIdAutoField"
        if os.getenv("DB_ENGINE") == "django_mongodb_backend"
        else "django.db.models.BigAutoField"
    )
    name = 'tickets'
    verbose_name = 'Complaint & Ticket Management System'

    def ready(self):
        """Import signals when app is ready."""
        import tickets.signals  # noqa
