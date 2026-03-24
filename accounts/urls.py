"""URL configuration for accounts app."""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("health/", views.AccountsHealthView.as_view(), name="health"),
]
