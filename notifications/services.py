"""Business services for notifications domain."""

from finance.models import Notification


def active_notifications_queryset():
    """Return active notifications ordered by recency."""
    return Notification.objects.filter(is_active=True).order_by("-created_at")
