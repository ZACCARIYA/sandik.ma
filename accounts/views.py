"""Views for account-domain endpoints (email verification, health)."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import signing
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404, render
from django.template.loader import render_to_string
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


def send_verification_email(request, user: User) -> bool:
    """Send an HTML verification email to the user. Returns True on success."""
    if not user.email:
        return False

    verify_url = build_verify_link(request, user)
    subject = "Vérifiez votre adresse email — SyndicPro"

    # Render HTML template
    html_message = render_to_string("emails/email_verify.html", {
        "user_name": user.get_full_name() or user.username,
        "user_email": user.email,
        "verify_url": verify_url,
        "app_name": "SyndicPro",
        "subject": subject,
    })

    # Plain-text fallback
    text_message = (
        f"Bonjour {user.get_full_name() or user.username},\n\n"
        f"Merci de vous être inscrit sur SyndicPro.\n"
        f"Veuillez confirmer votre adresse email en cliquant sur le lien suivant :\n"
        f"{verify_url}\n\n"
        f"Ce lien expirera dans 3 jours.\n"
        f"Cordialement,\nL'équipe SyndicPro"
    )

    try:
        return send_email(user.email, subject, text_message, html_message=html_message)
    except Exception:
        return False


class SendVerificationEmailView(LoginRequiredMixin, View):
    """Send or resend the verification email to the logged-in user."""

    def post(self, request, *args, **kwargs):
        user: User = request.user
        if not user.email:
            messages.error(request, "Aucune adresse email n'est associée à votre compte.")
            return redirect('finance:home')

        if send_verification_email(request, user):
            messages.success(request, "Email de vérification envoyé. Veuillez vérifier votre boîte de réception.")
        else:
            messages.error(request, "Impossible d'envoyer l'email de vérification pour le moment.")
        return redirect('finance:home')


class ResendVerificationView(View):
    """Public resend endpoint (no login required, used from check-your-email page)."""

    def post(self, request, *args, **kwargs):
        email = request.POST.get("email", "").strip()
        if not email:
            messages.error(request, "Adresse email manquante.")
            return redirect('finance:login')

        try:
            user = User.objects.get(email__iexact=email, is_active=False)
        except User.DoesNotExist:
            # Don't reveal whether the email exists — just show a generic success
            messages.success(request, "Si un compte est associé à cette adresse, un email a été envoyé.")
            return redirect('finance:email_check')

        if send_verification_email(request, user):
            messages.success(request, "Email de vérification renvoyé avec succès.")
        else:
            messages.error(request, "Impossible d'envoyer l'email pour le moment. Réessayez plus tard.")

        return render(request, 'finance/email_check.html', {'email': email})


class VerifyEmailView(View):
    """Validate a verification token and activate the user."""

    def get(self, request, *args, **kwargs):
        token = request.GET.get("t", "")
        if not token:
            return render(request, 'finance/email_verified.html', {
                'success': False,
                'error_title': 'Lien invalide',
                'error_message': 'Ce lien de vérification est invalide.',
            })

        try:
            payload = signing.loads(token, salt=SIGNING_SALT, max_age=TOKEN_MAX_AGE)
            user = get_object_or_404(User, pk=payload.get("uid"))

            # Check email matches
            if not user.email or user.email.lower() != str(payload.get("email", "")).lower():
                return render(request, 'finance/email_verified.html', {
                    'success': False,
                    'error_title': 'Lien invalide',
                    'error_message': 'Ce lien de vérification ne correspond à aucun compte.',
                })

            # Prevent reuse — already verified
            if user.email_verified and user.is_active:
                return render(request, 'finance/email_verified.html', {
                    'success': True,  # Show success anyway, they're already verified
                })

            # Activate and verify
            user.is_active = True
            user.email_verified = True
            user.email_verified_at = timezone.now()
            user.save()

            return render(request, 'finance/email_verified.html', {'success': True})

        except signing.SignatureExpired:
            return render(request, 'finance/email_verified.html', {
                'success': False,
                'error_title': 'Lien expiré',
                'error_message': 'Ce lien a expiré. Veuillez vous reconnecter et demander un nouvel email de vérification.',
            })
        except signing.BadSignature:
            return render(request, 'finance/email_verified.html', {
                'success': False,
                'error_title': 'Lien invalide',
                'error_message': 'Ce lien de vérification est invalide ou a été altéré.',
            })


class AccountsHealthView(View):
    """Simple health endpoint for account module wiring checks."""

    def get(self, request):
        return JsonResponse({"status": "ok", "module": "accounts"})
