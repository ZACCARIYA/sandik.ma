from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import signing
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views import View

from accounts.models import User
from finance.models import send_email  # reuse existing util


SIGNING_SALT = "accounts.email.verify"
TOKEN_MAX_AGE = 60 * 60 * 24 * 3  # 3 days


def build_verify_link(request, user: User) -> str:
	"""Create a signed verification URL for the given user."""
	payload = {"uid": str(user.pk), "email": user.email, "ts": timezone.now().timestamp()}
	token = signing.dumps(payload, salt=SIGNING_SALT)
	url = request.build_absolute_uri(f"{reverse('accounts:verify_email')}?t={token}")
	return url


class SendVerificationEmailView(LoginRequiredMixin, View):
	"""Send or resend the verification email to the logged-in user."""
	
	def post(self, request, *args, **kwargs):
		user: User = request.user
		if not user.email:
			messages.error(request, "Aucune adresse email n'est associée à votre compte.")
			return redirect('finance:home')
		
		verify_link = build_verify_link(request, user)
		subject = "Vérification de votre adresse email"
		body = (
			"Bonjour,\n\n"
			"Veuillez confirmer votre adresse email en cliquant sur le lien suivant:\n"
			f"{verify_link}\n\n"
			"Ce lien expirera dans 3 jours.\n"
			"Cordialement."
		)
		try:
			# Use existing helper; falls back to console in dev if configured
			send_email(user.email, subject, body)
			messages.success(request, "Email de vérification envoyé. Veuillez vérifier votre boîte de réception.")
		except Exception:
			messages.error(request, "Impossible d'envoyer l'email de vérification pour le moment.")
		return redirect('finance:home')


class VerifyEmailView(View):
	"""Validate a verification token and mark the user's email as verified."""
	
	def get(self, request, *args, **kwargs):
		token = request.GET.get("t", "")
		if not token:
			messages.error(request, "Lien de vérification invalide.")
			return redirect('finance:login')
		
		try:
			payload = signing.loads(token, salt=SIGNING_SALT, max_age=TOKEN_MAX_AGE)
			user = get_object_or_404(User, pk=payload.get("uid"))
			# Basic sanity check
			if not user.email or user.email.lower() != str(payload.get("email", "")).lower():
				messages.error(request, "Lien de vérification invalide.")
				return redirect('finance:login')
			
			user.email_verified = True
			user.email_verified_at = timezone.now()
			user.save()
			
			messages.success(request, "Votre adresse email a été vérifiée avec succès.")
			return redirect('finance:login')
		except signing.SignatureExpired:
			messages.error(request, "Le lien a expiré. Demandez un nouvel email de vérification.")
		except signing.BadSignature:
			messages.error(request, "Lien de vérification invalide.")
		
		return redirect('finance:login')

"""Views for account-domain endpoints."""

from django.http import JsonResponse
from django.views import View


class AccountsHealthView(View):
    """Simple health endpoint for account module wiring checks."""

    def get(self, request):
        return JsonResponse({"status": "ok", "module": "accounts"})
