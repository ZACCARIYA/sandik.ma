"""Resident-domain views."""

from django.http import JsonResponse
from django.views import View


class ResidentsHealthView(View):
    """Lightweight endpoint to validate app wiring."""

    def get(self, request):
        return JsonResponse({"status": "ok", "module": "residents"})
