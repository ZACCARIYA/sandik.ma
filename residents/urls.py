"""URL configuration for residents app."""

from django.urls import path

from .views import ResidentsHealthView

app_name = "residents"

urlpatterns = [
    path("health/", ResidentsHealthView.as_view(), name="health"),
]
