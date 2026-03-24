"""
Notification service for the Ticket system.

Handles email and SMS notifications for ticket events.
"""

from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth import get_user_model
import os

User = get_user_model()

# Mock SMS function - replace with actual provider
def send_sms(phone_number, message):
    """
    Send SMS notification.
    
    TODO: Integrate with SMS provider (Twilio, AWS SNS, Maroc Telecom API, etc.)
    For Moroccan market:
    - Maroc Telecom: https://www.maroctelecom.ma/en/business/
    - Orange Maroc: https://www.orange.ma/
    - Inwi: https://www.inwi.ma/
    """
    # This is a placeholder - implement your SMS provider integration
    print(f"[SMS] To {phone_number}: {message}")
    return True


class TicketNotificationService:
    """Service for sending ticket-related notifications."""
    
    @staticmethod
    def notify_ticket_created(ticket):
        """Send notification when ticket is created."""
        # Notify admins
        admins = User.objects.filter(role__in=['SYNDIC', 'SUPERADMIN'], is_active=True)
        
        for admin in admins:
            subject = f"New Ticket: {ticket.title} (#{ticket.id})"
            context = {
                'ticket': ticket,
                'recipient': admin,
                'action_url': f"/tickets/{ticket.id}/",
            }
            
            TicketNotificationService._send_email(
                subject=subject,
                template='tickets/emails/ticket_created_admin.html',
                context=context,
                recipient_email=admin.email
            )
        
        # Notify resident (confirmation)
        subject = f"Ticket Received: {ticket.title}"
        context = {
            'ticket': ticket,
            'recipient': ticket.resident,
        }
        
        TicketNotificationService._send_email(
            subject=subject,
            template='tickets/emails/ticket_created_resident.html',
            context=context,
            recipient_email=ticket.resident.email
        )
    
    @staticmethod
    def notify_status_changed(ticket, old_status, new_status):
        """Send notification when ticket status changes."""
        # Notify resident
        subject = f"Ticket #{ticket.id} - Status Updated to {new_status.upper()}"
        context = {
            'ticket': ticket,
            'old_status': old_status,
            'new_status': new_status,
            'recipient': ticket.resident,
        }
        
        TicketNotificationService._send_email(
            subject=subject,
            template='tickets/emails/ticket_status_changed.html',
            context=context,
            recipient_email=ticket.resident.email
        )
        
        # Notify assigned admin
        if ticket.assigned_to:
            subject = f"Ticket #{ticket.id} - Status: {new_status.upper()}"
            context = {
                'ticket': ticket,
                'old_status': old_status,
                'new_status': new_status,
                'recipient': ticket.assigned_to,
            }
            
            TicketNotificationService._send_email(
                subject=subject,
                template='tickets/emails/ticket_status_changed_admin.html',
                context=context,
                recipient_email=ticket.assigned_to.email
            )
    
    @staticmethod
    def notify_ticket_assigned(ticket, admin):
        """Send notification when ticket is assigned."""
        subject = f"New Ticket Assigned: {ticket.title}"
        context = {
            'ticket': ticket,
            'assigned_admin': admin,
            'resident_name': ticket.resident.get_full_name(),
        }
        
        TicketNotificationService._send_email(
            subject=subject,
            template='tickets/emails/ticket_assigned.html',
            context=context,
            recipient_email=admin.email
        )
    
    @staticmethod
    def notify_message_added(message):
        """Send notification when message is added to ticket."""
        ticket = message.ticket
        
        if message.is_internal:
            # Internal messages - notify admins only
            admins = User.objects.filter(role__in=['SYNDIC', 'SUPERADMIN'], is_active=True).exclude(pk=message.author.pk)
            recipient_list = list(admins.values_list('email', flat=True))
        else:
            # Public messages - notify relevant parties
            if message.author.role == 'RESIDENT':
                # Resident reply - notify assigned admin
                if ticket.assigned_to:
                    recipient_list = [ticket.assigned_to.email]
                else:
                    # Notify all admins if not assigned
                    admins = User.objects.filter(role__in=['SYNDIC', 'SUPERADMIN'], is_active=True)
                    recipient_list = list(admins.values_list('email', flat=True))
            else:
                # Admin reply - notify resident
                recipient_list = [ticket.resident.email]
        
        if recipient_list:
            subject = f"New Message on Ticket #{ticket.id}"
            context = {
                'ticket': ticket,
                'message': message,
                'author_name': message.author.get_full_name(),
            }
            
            for email in recipient_list:
                TicketNotificationService._send_email(
                    subject=subject,
                    template='tickets/emails/ticket_message_added.html',
                    context=context,
                    recipient_email=email
                )
    
    @staticmethod
    def notify_sla_breach(ticket):
        """Send notification when SLA is breached."""
        # Notify assigned admin
        if ticket.assigned_to:
            subject = f"⚠️ SLA Breached: Ticket #{ticket.id}"
            context = {
                'ticket': ticket,
                'sla_due_date': ticket.sla_due_date,
            }
            
            TicketNotificationService._send_email(
                subject=subject,
                template='tickets/emails/sla_breached.html',
                context=context,
                recipient_email=ticket.assigned_to.email
            )
        
        # Also notify all admins
        admins = User.objects.filter(role__in=['SYNDIC', 'SUPERADMIN'], is_active=True)
        for admin in admins:
            context = {
                'ticket': ticket,
                'sla_due_date': ticket.sla_due_date,
            }
            
            TicketNotificationService._send_email(
                subject=subject,
                template='tickets/emails/sla_breached_admin.html',
                context=context,
                recipient_email=admin.email
            )
    
    @staticmethod
    def _send_email(subject, template, context, recipient_email):
        """Generic email sender."""
        try:
            # Render template
            html_message = render_to_string(template, context)
            plain_message = strip_tags(html_message)
            
            # Send email
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                html_message=html_message,
                fail_silently=False,
            )
            
            return True
        except Exception as e:
            print(f"Error sending email to {recipient_email}: {str(e)}")
            return False
    
    @staticmethod
    def send_sms_notification(phone_number, message):
        """Send SMS notification (placeholder for integration)."""
        return send_sms(phone_number, message)
