"""URL configuration for documents app."""

from django.urls import path

from .views import DocumentsHealthView

app_name = "documents"

urlpatterns = [
    path("health/", DocumentsHealthView.as_view(), name="health"),
]
