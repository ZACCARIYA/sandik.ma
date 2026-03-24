"""Tickets app configuration."""

from django.apps import AppConfig


class TicketsConfig(AppConfig):
    """Configuration for the Tickets app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tickets'
    verbose_name = 'Complaint & Ticket Management System'

    def ready(self):
        """Import signals when app is ready."""
        import tickets.signals  # noqa
