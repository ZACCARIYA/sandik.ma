from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from finance.emails import send_templated_email
from finance.models import send_email
import os


class Command(BaseCommand):
    help = 'Test l\'envoi d\'emails avec différentes méthodes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Adresse email de destination pour le test',
            default='test@example.com'
        )
        parser.add_argument(
            '--method',
            type=str,
            choices=['simple', 'templated', 'model'],
            default='simple',
            help='Méthode d\'envoi à tester (simple, templated, model)'
        )

    def handle(self, *args, **options):
        recipient_email = options['email']
        method = options['method']
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Test d\'envoi d\'email ==='))
        self.stdout.write(f'Destination: {recipient_email}')
        self.stdout.write(f'Méthode: {method}')
        self.stdout.write(f'SEND_REAL_EMAILS: {os.getenv("SEND_REAL_EMAILS", "False")}')
        self.stdout.write(f'EMAIL_BACKEND: {os.getenv("EMAIL_BACKEND", "console")}')
        self.stdout.write('')

        try:
            if method == 'simple':
                self.test_simple_email(recipient_email)
            elif method == 'templated':
                self.test_templated_email(recipient_email)
            elif method == 'model':
                self.test_model_email(recipient_email)
            
            self.stdout.write(self.style.SUCCESS('\n✓ Test d\'envoi réussi !'))
            self.stdout.write('\nVérifiez votre boîte de réception ou la console Django.')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Erreur lors de l\'envoi: {e}'))
            self.stdout.write(self.style.WARNING('\nVérifiez votre configuration dans le fichier .env'))

    def test_simple_email(self, recipient_email):
        """Test avec send_mail de Django"""
        self.stdout.write('Envoi via send_mail (Django)...')
        result = send_mail(
            subject='Test Email - SyndicPro',
            message='Ceci est un test d\'envoi d\'email depuis SyndicPro.\n\nSi vous recevez cet email, la configuration est correcte !',
            from_email=None,  # Utilise DEFAULT_FROM_EMAIL
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        self.stdout.write(f'Résultat: {result} email(s) envoyé(s)')

    def test_templated_email(self, recipient_email):
        """Test avec send_templated_email"""
        self.stdout.write('Envoi via send_templated_email (template HTML)...')
        try:
            from django.urls import reverse
            from django.conf import settings
            base_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
            dashboard_url = base_url + reverse('finance:resident_dashboard')
        except Exception:
            dashboard_url = 'http://127.0.0.1:8000/resident-dashboard/'
        
        result = send_templated_email(
            subject='Test Email Template - SyndicPro',
            to_email=recipient_email,
            template_name='emails/notification_generic.html',
            context={
                'resident_name': 'Résident Test',
                'title': 'Test d\'envoi d\'email',
                'message': 'Ceci est un test d\'envoi d\'email avec template HTML depuis SyndicPro. Le montant et le lien d\'accès sont maintenant affichés.',
                'amount': 1500.00,
                'date': '29/01/2026',
                'notification_type': 'Notification de test',
                'priority': 'Moyenne',
                'dashboard_url': dashboard_url,
                'link': dashboard_url,
                'intro_text': 'Ceci est un email de test pour vérifier l\'affichage du montant et du lien d\'accès.',
            }
        )
        self.stdout.write(f'Résultat: {result} email(s) envoyé(s)')

    def test_model_email(self, recipient_email):
        """Test avec la fonction send_email du modèle"""
        self.stdout.write('Envoi via send_email (modèle finance)...')
        result = send_email(
            recipient_email=recipient_email,
            subject='Test Email Model - SyndicPro',
            message='Ceci est un test d\'envoi d\'email via la fonction send_email du modèle.',
        )
        self.stdout.write(f'Résultat: {"✓ Email envoyé" if result else "✗ Échec de l\'envoi"}')
