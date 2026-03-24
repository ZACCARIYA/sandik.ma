"""Notification-domain views."""

from django.http import JsonResponse
from django.views import View


class NotificationsHealthView(View):
    """Lightweight endpoint to validate app wiring."""

    def get(self, request):
        return JsonResponse({"status": "ok", "module": "notifications"})
