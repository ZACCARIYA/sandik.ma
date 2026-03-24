"""Business services for resident-domain operations."""

from accounts.models import User


def resident_queryset():
    """Base queryset for resident listing pages."""
    return User.objects.filter(role=User.Roles.RESIDENT).select_related("status")
