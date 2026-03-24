"""
Django signals for the Tickets app.

Handles automatic actions like SLA calculations, notifications, etc.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Ticket, TicketMessage, TicketActivityLog


@receiver(pre_save, sender=Ticket)
def ticket_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal handler for Ticket.
    
    - Calculate SLA if ticket is newly created
    - Auto-detect urgent keywords
    """
    if not instance.pk:
        # New ticket
        instance._calculate_sla()
        instance._detect_urgent_keywords()


@receiver(post_save, sender=Ticket)
def ticket_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal handler for Ticket.
    
    - Create activity log for new tickets
    """
    if created:
        TicketActivityLog.objects.create(
            ticket=instance,
            action='created',
            performed_by=instance.created_by or instance.resident,
            description=f"Ticket created by {instance.resident.get_full_name()}"
        )
