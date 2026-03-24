"""
Views for the Ticket & Complaint Management System.

Includes views for:
- Listing tickets (with filters and search)
- Creating tickets
- Viewing ticket details
- Managing ticket status and assignment
- Adding messages and attachments
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, DetailView, UpdateView, View, TemplateView
from django.urls import reverse_lazy, reverse
from django.contrib import messages as django_messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from django.http import JsonResponse, HttpResponseForbidden, Http404
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db import transaction
import json
from datetime import timedelta

from .models import (
    Ticket, TicketMessage, TicketAttachment, TicketCategory,
    TicketActivityLog
)
from .services.ticket_service import TicketService
from .services.notification_service import TicketNotificationService

User = get_user_model()


class TicketListView(LoginRequiredMixin, ListView):
    """
    List tickets based on user role.
    
    - Residents: Only see their own tickets
    - Admins: See all tickets with filtering and search
    """
    
    model = Ticket
    template_name = 'tickets/ticket_list.html'
    context_object_name = 'tickets'
    paginate_by = 20
    
    def get_queryset(self):
        """Filter tickets based on user role."""
        queryset = Ticket.objects.select_related(
            'resident', 'assigned_to', 'category'
        ).prefetch_related(
            'messages', 'attachments'
        )
        
        # Residents only see their own tickets
        if self.request.user.role == 'RESIDENT':
            queryset = queryset.filter(resident=self.request.user)
        # Admins see all tickets
        elif self.request.user.role not in ['SYNDIC', 'SUPERADMIN']:
            raise Http404("Access denied")
        
        # Apply filters
        queryset = self._apply_filters(queryset)
        queryset = self._apply_search(queryset)
        
        # Default ordering
        queryset = queryset.order_by('-created_at')
        
        return queryset
    
    def _apply_filters(self, queryset):
        """Apply status, priority, and category filters."""
        status = self.request.GET.get('status')
        priority = self.request.GET.get('priority')
        category = self.request.GET.get('category')
        assigned = self.request.GET.get('assigned')
        
        if status:
            queryset = queryset.filter(status=status)
        
        if priority:
            queryset = queryset.filter(priority=priority)
        
        if category:
            queryset = queryset.filter(category_id=category)
        
        # For admins only
        if self.request.user.role in ['SYNDIC', 'SUPERADMIN']:
            if assigned == 'unassigned':
                queryset = queryset.filter(assigned_to__isnull=True)
            elif assigned == 'assigned_to_me':
                queryset = queryset.filter(assigned_to=self.request.user)
        
        return queryset
    
    def _apply_search(self, queryset):
        """Apply search filter."""
        search = self.request.GET.get('q')
        
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(tags__icontains=search) |
                Q(apartment__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Add filter options and statistics to context."""
        context = super().get_context_data(**kwargs)
        
        # Add available filters
        context['categories'] = TicketCategory.objects.filter(is_active=True)
        context['statuses'] = Ticket.Status.choices
        context['priorities'] = Ticket.Priority.choices
        
        # Add current filters for UI
        context['current_status'] = self.request.GET.get('status', '')
        context['current_priority'] = self.request.GET.get('priority', '')
        context['current_category'] = self.request.GET.get('category', '')
        context['current_assigned'] = self.request.GET.get('assigned', '')
        context['current_search'] = self.request.GET.get('q', '')
        
        # Add statistics
        if self.request.user.role in ['SYNDIC', 'SUPERADMIN']:
            base_qs = Ticket.objects.all()
        else:
            base_qs = Ticket.objects.filter(resident=self.request.user)
        
        context['stats'] = {
            'total_open': base_qs.filter(status=Ticket.Status.OPEN).count(),
            'total_in_progress': base_qs.filter(status=Ticket.Status.IN_PROGRESS).count(),
            'total_resolved': base_qs.filter(status=Ticket.Status.RESOLVED).count(),
            'urgent_open': base_qs.filter(status=Ticket.Status.OPEN, priority=Ticket.Priority.URGENT).count(),
        }
        
        return context


class TicketCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new ticket.
    
    Only residents can create tickets for themselves.
    """
    
    model = Ticket
    template_name = 'tickets/ticket_form.html'
    fields = ['title', 'description', 'category', 'priority']
    
    def dispatch(self, request, *args, **kwargs):
        """Only residents can create tickets."""
        if request.user.role != 'RESIDENT':
            django_messages.error(request, 'Only residents can create tickets.')
            return redirect('tickets:list')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add categories to context."""
        context = super().get_context_data(**kwargs)
        context['categories'] = TicketCategory.objects.filter(is_active=True)
        return context
    
    def form_valid(self, form):
        """Set resident and create ticket."""
        form.instance.resident = self.request.user
        form.instance.created_by = self.request.user
        
        # Auto-detect apartment
        form.instance.apartment = self.request.user.apartment
        
        response = super().form_valid(form)
        
        # Log activity
        TicketActivityLog.objects.create(
            ticket=self.object,
            action='created',
            performed_by=self.request.user,
            description=f"Ticket created by {self.request.user}"
        )
        
        # Send notification
        TicketNotificationService.notify_ticket_created(self.object)
        
        django_messages.success(
            self.request,
            f'Ticket "{self.object.title}" created successfully. Ref: #{self.object.id}'
        )
        
        return response
    
    def get_success_url(self):
        """Redirect to ticket detail."""
        return reverse_lazy('tickets:detail', kwargs={'pk': self.object.pk})


class TicketDetailView(LoginRequiredMixin, DetailView):
    """
    Display ticket details and messages.
    
    Includes permission checks for residents vs admins.
    """
    
    model = Ticket
    template_name = 'tickets/ticket_detail.html'
    context_object_name = 'ticket'
    
    def get_queryset(self):
        """Filter based on user role."""
        queryset = Ticket.objects.select_related(
            'resident', 'assigned_to', 'category', 'created_by'
        ).prefetch_related(
            Prefetch(
                'messages',
                TicketMessage.objects.select_related('author').order_by('created_at')
            ),
            'attachments'
        )
        
        if self.request.user.role == 'RESIDENT':
            queryset = queryset.filter(resident=self.request.user)
        elif self.request.user.role not in ['SYNDIC', 'SUPERADMIN']:
            raise Http404("Access denied")
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Add messages and activity log to context."""
        context = super().get_context_data(**kwargs)
        
        ticket = self.object
        
        # Get messages with proper filtering
        if self.request.user.role == 'RESIDENT':
            # Residents don't see internal notes
            context['messages'] = ticket.messages.filter(is_internal=False)
        else:
            # Admins see all messages
            context['messages'] = ticket.messages.all()
        
        context['activity_log'] = ticket.activity_logs.all()[:10]
        context['statuses'] = Ticket.Status.choices
        context['priorities'] = Ticket.Priority.choices
        
        # Add available actions based on user role and ticket status
        context['can_edit'] = self._can_edit_ticket(ticket)
        context['can_assign'] = self._can_assign_ticket(ticket)
        context['can_change_status'] = self._can_change_status(ticket)
        
        # Get available admins for assignment
        if self.request.user.role in ['SYNDIC', 'SUPERADMIN']:
            context['available_admins'] = User.objects.filter(
                role__in=['SYNDIC', 'SUPERADMIN'],
                is_active=True
            ).exclude(pk=ticket.assigned_to_id if ticket.assigned_to else None)
        
        return context
    
    def _can_edit_ticket(self, ticket):
        """Check if user can edit ticket."""
        if self.request.user.role in ['SYNDIC', 'SUPERADMIN']:
            return True
        return False
    
    def _can_assign_ticket(self, ticket):
        """Check if user can assign ticket."""
        return self.request.user.role in ['SYNDIC', 'SUPERADMIN']
    
    def _can_change_status(self, ticket):
        """Check if user can change ticket status."""
        return self.request.user.role in ['SYNDIC', 'SUPERADMIN']


class TicketUpdateStatusView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Update ticket status (admin only)."""
    
    def test_func(self):
        """Only admins can update status."""
        return self.request.user.role in ['SYNDIC', 'SUPERADMIN']
    
    def post(self, request, pk):
        """Handle status update."""
        ticket = get_object_or_404(Ticket, pk=pk)
        new_status = request.POST.get('status')
        
        if new_status not in dict(Ticket.Status.choices):
            django_messages.error(request, 'Invalid status.')
            return redirect('tickets:detail', pk=ticket.pk)
        
        old_status = ticket.status
        ticket.status = new_status
        
        # Update timestamps
        if new_status == Ticket.Status.RESOLVED:
            ticket.resolved_at = timezone.now()
        elif new_status == Ticket.Status.CLOSED:
            ticket.closed_at = timezone.now()
        elif new_status == Ticket.Status.REOPENED:
            ticket.resolved_at = None
            ticket.closed_at = None
        
        ticket.save()
        
        # Log activity
        TicketActivityLog.objects.create(
            ticket=ticket,
            action='status_changed',
            performed_by=request.user,
            old_value=old_status,
            new_value=new_status,
            description=f"Status changed from {old_status} to {new_status}"
        )
        
        # Send notification
        TicketNotificationService.notify_status_changed(ticket, old_status, new_status)
        
        django_messages.success(request, f'Ticket status updated to {new_status}.')
        
        return redirect('tickets:detail', pk=ticket.pk)


class TicketAssignView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Assign ticket to admin (admin only)."""
    
    def test_func(self):
        """Only admins can assign tickets."""
        return self.request.user.role in ['SYNDIC', 'SUPERADMIN']
    
    def post(self, request, pk):
        """Handle ticket assignment."""
        ticket = get_object_or_404(Ticket, pk=pk)
        admin_id = request.POST.get('admin_id')
        
        if admin_id:
            admin = get_object_or_404(
                User,
                pk=admin_id,
                role__in=['SYNDIC', 'SUPERADMIN'],
                is_active=True
            )
            old_assigned = ticket.assigned_to
            ticket.assigned_to = admin
            
            # Auto-mark as in progress if being assigned
            if ticket.status == Ticket.Status.OPEN:
                ticket.status = Ticket.Status.IN_PROGRESS
            
            ticket.save()
            
            # Log activity
            old_name = old_assigned.get_full_name() if old_assigned else 'Unassigned'
            TicketActivityLog.objects.create(
                ticket=ticket,
                action='assigned',
                performed_by=request.user,
                old_value=old_name,
                new_value=admin.get_full_name(),
                description=f"Assigned to {admin.get_full_name()}"
            )
            
            # Send notification
            TicketNotificationService.notify_ticket_assigned(ticket, admin)
            
            django_messages.success(request, f'Ticket assigned to {admin.get_full_name()}.')
        else:
            ticket.assigned_to = None
            ticket.save()
            django_messages.success(request, 'Ticket unassigned.')
        
        return redirect('tickets:detail', pk=ticket.pk)


class TicketMessageCreateView(LoginRequiredMixin, CreateView):
    """Add a message to a ticket."""
    
    model = TicketMessage
    fields = ['message', 'is_internal']
    template_name = 'tickets/message_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Get ticket and check permissions."""
        self.ticket = get_object_or_404(Ticket, pk=self.kwargs['ticket_pk'])
        
        # Check permission
        if request.user.role == 'RESIDENT' and self.ticket.resident != request.user:
            raise Http404("Access denied")
        elif request.user.role not in ['RESIDENT', 'SYNDIC', 'SUPERADMIN']:
            raise Http404("Access denied")
        
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Attach message to ticket."""
        form.instance.ticket = self.ticket
        form.instance.author = self.request.user
        
        # Residents can't create internal messages
        if self.request.user.role == 'RESIDENT':
            form.instance.is_internal = False
        
        response = super().form_valid(form)
        
        # Log activity
        TicketActivityLog.objects.create(
            ticket=self.ticket,
            action='commented',
            performed_by=self.request.user,
            description=f"Message added by {self.request.user.get_full_name()}"
        )
        
        # Send notification
        TicketNotificationService.notify_message_added(self.object)
        
        django_messages.success(self.request, 'Message added successfully.')
        
        return response
    
    def get_success_url(self):
        """Redirect to ticket detail."""
        return reverse_lazy('tickets:detail', kwargs={'pk': self.ticket.pk})


class TicketAttachmentUploadView(LoginRequiredMixin, View):
    """Handle file uploads for tickets."""
    
    def post(self, request, ticket_pk):
        """Handle AJAX file upload."""
        try:
            ticket = get_object_or_404(Ticket, pk=ticket_pk)
            
            # Check permission
            if request.user.role == 'RESIDENT' and ticket.resident != request.user:
                return JsonResponse({'error': 'Access denied'}, status=403)
            elif request.user.role not in ['RESIDENT', 'SYNDIC', 'SUPERADMIN']:
                return JsonResponse({'error': 'Access denied'}, status=403)
            
            if 'file' not in request.FILES:
                return JsonResponse({'error': 'No file uploaded'}, status=400)
            
            file = request.FILES['file']
            message_id = request.POST.get('message_id')
            
            # Validate file
            if file.size > 10 * 1024 * 1024:  # 10MB limit
                return JsonResponse({'error': 'File too large (max 10MB)'}, status=400)
            
            # Get message if provided
            message = None
            if message_id:
                message = get_object_or_404(TicketMessage, pk=message_id, ticket=ticket)
            
            # Create attachment
            attachment = TicketAttachment.objects.create(
                ticket=ticket,
                message=message,
                file=file,
                uploaded_by=request.user,
                file_name=file.name,
                file_size=file.size,
                file_type=file.content_type
            )
            
            # Log activity
            TicketActivityLog.objects.create(
                ticket=ticket,
                action='attachment_added',
                performed_by=request.user,
                description=f"Attachment '{file.name}' added"
            )
            
            return JsonResponse({
                'id': attachment.id,
                'name': attachment.file_name,
                'size': attachment.get_file_size_display(),
                'url': attachment.file.url
            })
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


class TicketDashboardView(LoginRequiredMixin, TemplateView):
    """
    Dashboard widget showing ticket statistics.
    
    - Residents: Their own ticket stats
    - Admins: System-wide stats
    """
    
    template_name = 'tickets/dashboard.html'
    
    def get_context_data(self, **kwargs):
        """Build dashboard context."""
        context = super().get_context_data(**kwargs)
        
        if self.request.user.role == 'RESIDENT':
            base_qs = Ticket.objects.filter(resident=self.request.user)
        else:
            base_qs = Ticket.objects.all()
        
        # Calculate stats
        stats = {
            'total_tickets': base_qs.count(),
            'open_tickets': base_qs.filter(status=Ticket.Status.OPEN).count(),
            'in_progress_tickets': base_qs.filter(status=Ticket.Status.IN_PROGRESS).count(),
            'resolved_tickets': base_qs.filter(status=Ticket.Status.RESOLVED).count(),
            'closed_tickets': base_qs.filter(status=Ticket.Status.CLOSED).count(),
            'urgent_tickets': base_qs.filter(priority=Ticket.Priority.URGENT).count(),
            'overdue_sla_tickets': base_qs.filter(sla_breached=True).count(),
        }
        
        # Recent tickets
        recent_tickets = base_qs.select_related(
            'resident', 'assigned_to', 'category'
        ).order_by('-created_at')[:5]
        
        # Tickets needing attention
        attention_needed = base_qs.filter(
            Q(status=Ticket.Status.OPEN) |
            (Q(status=Ticket.Status.IN_PROGRESS) & Q(sla_breached=True))
        ).select_related('resident', 'assigned_to')[:5]
        
        context.update({
            'stats': stats,
            'recent_tickets': recent_tickets,
            'attention_needed': attention_needed,
        })
        
        return context
