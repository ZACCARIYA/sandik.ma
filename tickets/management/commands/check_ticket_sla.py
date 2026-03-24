"""
Management command to check SLA status for tickets.

Usage: python manage.py check_ticket_sla
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from tickets.services.ticket_service import TicketService
from tickets.services.notification_service import TicketNotificationService


class Command(BaseCommand):
    """Check and update SLA status for tickets."""
    
    help = 'Check SLA status for open tickets and send notifications for breaches'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--notify',
            action='store_true',
            dest='notify',
            help='Send notifications for breached SLAs',
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        self.stdout.write("Checking ticket SLA status...")
        
        # Check and update SLA status
        breached_count = TicketService.check_and_update_sla_status()
        
        self.stdout.write(
            self.style.SUCCESS(f"Updated {breached_count} tickets with SLA breaches")
        )
        
        # Send notifications if requested
        if options['notify']:
            self.stdout.write("Sending SLA breach notifications...")
            from tickets.models import Ticket
            
            breached_tickets = Ticket.objects.filter(sla_breached=True)
            notify_count = 0
            
            for ticket in breached_tickets:
                try:
                    TicketNotificationService.notify_sla_breach(ticket)
                    notify_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"Error notifying for ticket {ticket.id}: {str(e)}")
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f"Sent {notify_count} SLA breach notifications")
            )
