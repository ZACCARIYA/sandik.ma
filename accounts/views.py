"""Views for account-domain endpoints."""

from django.http import JsonResponse
from django.views import View


class AccountsHealthView(View):
    """Simple health endpoint for account module wiring checks."""

    def get(self, request):
        return JsonResponse({"status": "ok", "module": "accounts"})
