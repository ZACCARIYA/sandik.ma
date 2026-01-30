from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Document, Payment, Notification, OperationLog, Depense
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import os


def send_email_to_resident(subject: str, message: str, recipient_email: str) -> int:
    """Send an email to a resident using configured SMTP settings.

    Returns number of successfully delivered messages (0 or 1).
    """
    return send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER),
        recipient_list=[recipient_email],
        fail_silently=False,
    )


@receiver(post_save, sender=Document)
def send_document_email(sender, instance: Document, created: bool, **kwargs):
    """Notify resident by email when a new document is created (HTML template)."""
    if not created:
        return
    if not instance.resident or not instance.resident.email:
        return

    # Construire un lien vers le document si possible
    try:
        from django.urls import reverse
        base_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        link = base_url + reverse('finance:document_detail', args=[instance.pk])
    except Exception:
        link = None

    subject = f"Nouveau document: {instance.title}"
    # Construire le lien vers le dashboard résident
    try:
        from django.urls import reverse
        base_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        dashboard_url = base_url + reverse('finance:resident_dashboard')
    except Exception:
        dashboard_url = 'http://127.0.0.1:8000/resident-dashboard/'
    
    context = {
        'subject': subject,
        'resident_name': (instance.resident.get_full_name() or instance.resident.username),
        'document_type': instance.get_document_type_display(),
        'amount': instance.amount,
        'date': instance.date,
        'message': getattr(instance, 'description', '') or '',
        'link': link,
        'dashboard_url': dashboard_url,
        'intro_text': "Un nouveau document a été ajouté à votre espace.",
    }
    try:
        from .emails import send_templated_email
        send_templated_email(
            subject=subject,
            to_email=instance.resident.email,
            template_name='emails/document_added.html',
            context=context,
        )
    except Exception:
        # Fallback simple texte si le HTML échoue
        try:
            message = (
                f"Bonjour {context['resident_name']},\n\n"
                f"Un nouveau document a été ajouté à votre espace.\n"
                f"Type: {context['document_type']}\nMontant: {context['amount']} DH\nDate: {context['date']}\n"
                f"Lien: {link or ''}"
            )
            send_email_to_resident(subject, message, instance.resident.email)
        except Exception:
            pass
    try:
        OperationLog.objects.create(
            action='DOCUMENT_CREATED',
            actor=instance.uploaded_by,
            target_id=str(instance.pk),
            target_type='Document',
            meta={'title': instance.title, 'resident': instance.resident_id}
        )
    except Exception:
        pass


@receiver(post_save, sender=Document)
def create_in_app_notification_for_document(sender, instance: Document, created: bool, **kwargs):
    """Create in-app notification when a document is uploaded for a resident."""
    if not created:
        return
    try:
        notif = Notification.objects.create(
            title=f"Nouveau document: {instance.title}",
            message=f"Type: {instance.get_document_type_display()} • Montant: {instance.amount} DH • Date: {instance.date}",
            notification_type="DOCUMENT_UPLOADED",
            priority="MEDIUM",
            sender=instance.uploaded_by,
            is_active=True,
        )
        notif.recipients.add(instance.resident)
        # L'email est déjà envoyé via send_document_email, donc on marque cette notification
        # pour éviter le double envoi via le signal send_notification_email_auto
        notif._email_already_sent = True
    except Exception as e:
        print(f"Erreur création notification document: {e}")
        pass


@receiver(post_save, sender=Payment)
def notify_syndic_on_payment(sender, instance: Payment, created: bool, **kwargs):
    """When a resident records a payment, notify syndic via in-app (and email if available)."""
    if not created:
        return
    document = instance.document
    syndic_users = []
    if document:
        # Prefer the uploader as a target syndic
        if document.uploaded_by and document.uploaded_by.role in ["SYNDIC", "SUPERADMIN"]:
            syndic_users = [document.uploaded_by]
    
    # Fallback: notify all staff (syndic/superadmin)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if not syndic_users:
        syndic_users = list(User.objects.filter(role__in=["SYNDIC", "SUPERADMIN"]))

    # Create in-app notification
    try:
        title = "Paiement reçu"
        message = f"Montant: {instance.amount} DH • Date: {instance.payment_date} • Méthode: {instance.get_payment_method_display()}"
        notif = Notification.objects.create(
            title=title,
            message=message,
            notification_type="GENERAL_ANNOUNCEMENT",
            priority="HIGH",
            sender=document.resident if document else None,
            is_active=True,
        )
        notif.recipients.add(*syndic_users)
    except Exception:
        pass

    # Optional: send email to primary syndic
    try:
        primary = syndic_users[0]
        if primary and primary.email:
            send_email_to_resident(
                subject="Paiement reçu",
                message=f"Un paiement a été enregistré. {message}",
                recipient_email=primary.email,
            )
    except Exception:
        pass




@receiver(post_save, sender=Depense)
def notify_residents_on_grosse_depense(sender, instance: Depense, created: bool, **kwargs):
    """Notifier tous les résidents quand une grosse dépense est ajoutée."""
    if not created or not instance.is_grosse_depense:
        return
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Récupérer tous les résidents
    residents = User.objects.filter(role='RESIDENT')
    
    if not residents.exists():
        return
    
    try:
        # Créer la notification in-app
        notif = Notification.objects.create(
            title="Nouvelle dépense importante",
            message=f"{instance.titre} • {instance.get_categorie_display()} • {instance.montant} DH • {instance.date_depense}",
            notification_type="GENERAL_ANNOUNCEMENT",
            priority="HIGH",
            sender=instance.ajoute_par,
            is_active=True,
        )
        notif.recipients.add(*residents)
        
        # Envoyer un email à tous les résidents (optionnel)
        for resident in residents:
            if resident.email:
                subject = "Nouvelle dépense importante pour l'immeuble"
                message = (
                    f"Bonjour {resident.get_full_name() or resident.username},\n\n"
                    f"Une nouvelle dépense importante a été enregistrée :\n\n"
                    f"Titre: {instance.titre}\n"
                    f"Catégorie: {instance.get_categorie_display()}\n"
                    f"Montant: {instance.montant} DH\n"
                    f"Date: {instance.date_depense}\n"
                    f"Description: {instance.description or 'Aucune description'}\n\n"
                    f"Connectez-vous pour consulter le détail des dépenses."
                )
                send_email_to_resident(subject, message, resident.email)
                
    except Exception as e:
        # Log l'erreur mais ne pas planter
        print(f"Erreur lors de l'envoi des notifications de dépense: {e}")
        pass


@receiver(post_save, sender=Notification)
def send_notification_email_auto(sender, instance: Notification, created: bool, **kwargs):
    """Send email automatically when a notification is created (if not already sent via NotificationCreateView)."""
    if not created:
        return
    
    # Vérifier si SEND_REAL_EMAILS est activé
    if os.getenv("SEND_REAL_EMAILS", "False") != "True":
        print(f"[NOTIFICATION EMAIL] SEND_REAL_EMAILS désactivé, email non envoyé pour: {instance.title}")
        return
    
    # Ne pas envoyer si l'email a déjà été envoyé via NotificationCreateView
    # On utilise un flag pour éviter les doubles envois
    if hasattr(instance, '_email_already_sent'):
        print(f"[NOTIFICATION EMAIL] Email déjà envoyé pour: {instance.title}")
        return
    
    # Envoyer un email à chaque destinataire résident
    recipients_count = 0
    for recipient in instance.recipients.all():
        if not recipient.email:
            print(f"[NOTIFICATION EMAIL] Résident {recipient.username} n'a pas d'email")
            continue
        
        if recipient.role != 'RESIDENT':
            print(f"[NOTIFICATION EMAIL] {recipient.username} n'est pas un résident (role: {recipient.role})")
            continue
        
        try:
            from .emails import send_templated_email
            from django.urls import reverse
            from django.conf import settings
            
            base_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
            dashboard_url = base_url + reverse('finance:resident_dashboard')
            
            context = {
                'subject': instance.title,
                'resident_name': (recipient.get_full_name() or recipient.username),
                'message': instance.message,
                'dashboard_url': dashboard_url,
                'notification_type': instance.get_notification_type_display() if hasattr(instance, 'get_notification_type_display') else None,
                'priority': instance.get_priority_display() if hasattr(instance, 'get_priority_display') else None,
                'intro_text': "Vous avez reçu une nouvelle notification.",
            }
            
            result = send_templated_email(
                subject=instance.title,
                to_email=recipient.email,
                template_name='emails/notification_generic.html',
                context=context,
            )
            recipients_count += 1
            print(f"[NOTIFICATION EMAIL] Email envoyé à {recipient.email} pour notification: {instance.title}")
        except Exception as e:
            print(f"[NOTIFICATION EMAIL] Erreur envoi email à {recipient.email}: {e}")
            import traceback
            traceback.print_exc()
    
    if recipients_count > 0:
        print(f"[NOTIFICATION EMAIL] {recipients_count} email(s) envoyé(s) pour la notification: {instance.title}")





