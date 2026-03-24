"""
Business logic services for the Ticket system.

TicketService handles core ticket operations and queries.
"""

from django.db.models import Q, Count, F, Prefetch
from django.utils import timezone
from datetime import timedelta
from ..models import Ticket, TicketMessage, TicketAttachment, TicketActivityLog


class TicketService:
    """Service class for ticket-related business logic."""
    
    @staticmethod
    def get_resident_tickets(resident):
        """Get all tickets for a resident with optimizations."""
        return Ticket.objects.filter(
            resident=resident
        ).select_related(
            'assigned_to', 'category', 'created_by'
        ).prefetch_related(
            'messages', 'attachments', 'activity_logs'
        ).order_by('-created_at')
    
    @staticmethod
    def get_admin_tickets(admin=None, filters=None):
        """Get all tickets for admin dashboard."""
        qs = Ticket.objects.select_related(
            'resident', 'assigned_to', 'category', 'created_by'
        ).prefetch_related(
            'messages', 'attachments'
        )
        
        if admin:
            qs = qs.filter(assigned_to=admin)
        
        if filters:
            if filters.get('status'):
                qs = qs.filter(status=filters['status'])
            if filters.get('priority'):
                qs = qs.filter(priority=filters['priority'])
            if filters.get('search'):
                search = filters['search']
                qs = qs.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search)
                )
        
        return qs.order_by('-created_at')
    
    @staticmethod
    def get_open_tickets():
        """Get all open tickets."""
        return Ticket.objects.filter(
            status__in=[Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS]
        ).select_related('resident', 'assigned_to')
    
    @staticmethod
    def get_urgent_tickets():
        """Get all urgent tickets."""
        return Ticket.objects.filter(
            priority=Ticket.Priority.URGENT,
            status__in=[Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS]
        ).select_related('resident', 'assigned_to')
    
    @staticmethod
    def get_overdue_tickets():
        """Get tickets that have breached SLA."""
        now = timezone.now()
        return Ticket.objects.filter(
            sla_due_date__lt=now,
            status__in=[Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS]
        ).select_related('resident', 'assigned_to')
    
    @staticmethod
    def get_unassigned_tickets():
        """Get tickets not assigned to anyone."""
        return Ticket.objects.filter(
            assigned_to__isnull=True,
            status__in=[Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS]
        ).select_related('resident')
    
    @staticmethod
    def check_and_update_sla_status():
        """
        Check and update SLA breach status for all open tickets.
        Call this periodically (e.g., via Celery task or cron job).
        """
        now = timezone.now()
        
        # Get all open tickets
        tickets = Ticket.objects.filter(
            status__in=[Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS],
            sla_due_date__isnull=False
        )
        
        # Update SLA breach status
        breached_count = 0
        for ticket in tickets:
            if ticket.sla_due_date < now and not ticket.sla_breached:
                ticket.sla_breached = True
                ticket.save(update_fields=['sla_breached'])
                breached_count += 1
        
        return breached_count
    
    @staticmethod
    def get_ticket_response_time_avg(admin=None):
        """
        Calculate average response time for tickets.
        Response time = time of first staff message - ticket creation time
        """
        from .models import User
        
        # Get first staff response for each ticket
        tickets = Ticket.objects.all()
        if admin:
            tickets = tickets.filter(assigned_to=admin)
        
        response_times = []
        for ticket in tickets[:100]:  # Limit to recent 100
            first_message = ticket.messages.filter(
                author__role__in=['SYNDIC', 'SUPERADMIN']
            ).first()
            
            if first_message:
                response_time = first_message.created_at - ticket.created_at
                response_times.append(response_time.total_seconds() / 3600)  # Convert to hours
        
        if response_times:
            return sum(response_times) / len(response_times)
        return 0
    
    @staticmethod
    def auto_assign_tickets_to_category_expert(ticket):
        """
        Auto-assign tickets to category experts if configured.
        Future enhancement for intelligent routing.
        """
        # TODO: Implement category-based auto-assignment
        # This could use a many-to-many relationship between categories and admins
        pass
    
    @staticmethod
    def get_ticket_stats(user=None):
        """Get comprehensive ticket statistics."""
        if user and user.role == 'RESIDENT':
            base_qs = Ticket.objects.filter(resident=user)
        else:
            base_qs = Ticket.objects.all()
        
        return {
            'total_tickets': base_qs.count(),
            'open_tickets': base_qs.filter(status=Ticket.Status.OPEN).count(),
            'in_progress_tickets': base_qs.filter(status=Ticket.Status.IN_PROGRESS).count(),
            'resolved_tickets': base_qs.filter(status=Ticket.Status.RESOLVED).count(),
            'closed_tickets': base_qs.filter(status=Ticket.Status.CLOSED).count(),
            'urgent_tickets': base_qs.filter(priority=Ticket.Priority.URGENT).count(),
            'urgent_and_open': base_qs.filter(
                priority=Ticket.Priority.URGENT,
                status=Ticket.Status.OPEN
            ).count(),
            'overdue_sla': base_qs.filter(sla_breached=True).count(),
            'unassigned': base_qs.filter(assigned_to__isnull=True).count(),
        }
