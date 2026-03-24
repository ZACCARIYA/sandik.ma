"""Service layer utilities for the accounts app."""

from accounts.models import User


def list_resident_accounts():
    """Return active resident accounts ordered for UI lists."""
    return User.objects.filter(role=User.Roles.RESIDENT).order_by("first_name", "username")
