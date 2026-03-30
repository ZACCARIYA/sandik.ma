"""URL configuration for accounts app."""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
	path("health/", views.AccountsHealthView.as_view(), name="health"),
	path("verify-email/", views.VerifyEmailView.as_view(), name="verify_email"),
	path("send-verification/", views.SendVerificationEmailView.as_view(), name="send_verification"),
]
