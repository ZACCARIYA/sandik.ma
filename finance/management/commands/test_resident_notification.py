from django.core.management.base import BaseCommand
from accounts.models import User
from finance.models import Notification
from finance.emails import send_templated_email
from django.urls import reverse
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Test l\'envoi de notifications aux résidents'

    def add_arguments(self, parser):
        parser.add_argument(
            '--resident',
            type=str,
            help='Username ou email du résident',
            default=None
        )

    def handle(self, *args, **options):
        resident_identifier = options['resident']
        
        # Trouver le résident
        from django.db.models import Q
        if resident_identifier:
            try:
                resident = User.objects.filter(
                    role='RESIDENT',
                    email__isnull=False
                ).filter(
                    Q(username=resident_identifier) | 
                    Q(email=resident_identifier)
                ).first()
            except:
                resident = None
        else:
            resident = User.objects.filter(role='RESIDENT', email__isnull=False).first()
        
        if not resident:
            self.stdout.write(self.style.ERROR('Aucun résident avec email trouvé'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Test notification résident ==='))
        self.stdout.write(f'Résident: {resident.username} ({resident.email})')
        self.stdout.write(f'SEND_REAL_EMAILS: {os.getenv("SEND_REAL_EMAILS", "False")}')
        self.stdout.write('')
        
        # Créer une notification de test
        try:
            from accounts.models import User as UserModel
            sender = UserModel.objects.filter(role__in=['SUPERADMIN', 'SYNDIC']).first()
            if not sender:
                sender = UserModel.objects.first()
            
            base_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
            dashboard_url = base_url + reverse('finance:resident_dashboard')
            
            # Créer la notification
            notification = Notification.objects.create(
                title='Test de notification',
                message='Ceci est un test pour vérifier que vous recevez bien les notifications par email.',
                notification_type='GENERAL_ANNOUNCEMENT',
                priority='MEDIUM',
                sender=sender,
                is_active=True,
            )
            notification.recipients.add(resident)
            
            self.stdout.write(f'✓ Notification créée: {notification.title}')
            
            # Envoyer l'email
            context = {
                'subject': notification.title,
                'resident_name': (resident.get_full_name() or resident.username),
                'message': notification.message,
                'dashboard_url': dashboard_url,
                'notification_type': 'Annonce générale',
                'priority': 'Moyenne',
                'intro_text': 'Ceci est un test de notification.',
            }
            
            result = send_templated_email(
                subject=notification.title,
                to_email=resident.email,
                template_name='emails/notification_generic.html',
                context=context,
            )
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ Email envoyé avec succès !'))
            self.stdout.write(f'Vérifiez la boîte de réception de {resident.email}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Erreur: {e}'))
            import traceback
            traceback.print_exc()
