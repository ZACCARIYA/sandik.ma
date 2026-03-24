"""
Ticket & Complaint Management Models

This module contains the core data models for the Complaint & Ticket System.
Includes Ticket, TicketMessage, and TicketAttachment models with full audit trail.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.utils.text import slugify
import os

User = get_user_model()


class TicketCategory(models.Model):
    """Categories for tickets (water, electricity, elevator, etc.)"""
    
    name_en = models.CharField(max_length=100, unique=True)
    name_ar = models.CharField(max_length=100, unique=True, blank=True)
    name_fr = models.CharField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon class or emoji")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Ticket Categories"
        ordering = ['name_en']
    
    def __str__(self):
        return self.name_en


class Ticket(models.Model):
    """
    Main Ticket model for complaint/issue tracking.
    
    Tracks the lifecycle of a ticket from creation to resolution.
    Supports status workflow, priority levels, and SLA tracking.
    """
    
    class Status(models.TextChoices):
        """Ticket status workflow"""
        OPEN = 'open', 'Open'
        IN_PROGRESS = 'in_progress', 'In Progress'
        RESOLVED = 'resolved', 'Resolved'
        CLOSED = 'closed', 'Closed'
        REOPENED = 'reopened', 'Reopened'
    
    class Priority(models.TextChoices):
        """Priority levels for tickets"""
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'
    
    # Core fields
    title = models.CharField(max_length=255, db_index=True)
    description = models.TextField()
    category = models.ForeignKey(TicketCategory, on_delete=models.SET_NULL, null=True, related_name='tickets')
    
    # Status & Priority
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True
    )
    
    # Assignment & Ownership
    resident = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reported_tickets',
        limit_choices_to={'role': 'RESIDENT'}
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        limit_choices_to={'role__in': ['SYNDIC', 'SUPERADMIN']}
    )
    
    # Location
    apartment = models.CharField(
        max_length=50,
        blank=True,
        help_text="Apartment/Lot number - auto-populated from resident"
    )
    
    # SLA & Tracking
    is_urgent_auto_detected = models.BooleanField(
        default=False,
        help_text="Auto-detected urgent ticket based on keywords"
    )
    sla_due_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="SLA target resolution time"
    )
    sla_breached = models.BooleanField(
        default=False,
        db_index=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tickets'
    )
    
    # Metadata
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    internal_notes = models.TextField(blank=True, help_text="Private notes for staff only")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['resident', 'status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['priority', '-created_at']),
            models.Index(fields=['sla_breached', 'status']),
        ]
    
    def __str__(self):
        return f"[{self.get_priority_display()}] {self.title}"
    
    def save(self, *args, **kwargs):
        """Override save to auto-populate apartment from resident."""
        if not self.apartment and self.resident:
            self.apartment = self.resident.apartment
        
        # Auto-detect urgent keywords
        self._detect_urgent_keywords()
        
        # Calculate SLA
        self._calculate_sla()
        
        super().save(*args, **kwargs)
    
    def _detect_urgent_keywords(self):
        """Auto-detect urgent tickets based on keywords."""
        urgent_keywords = [
            'leak', 'water', 'flood', 'fire', 'gas', 'safety',
            'emergency', 'danger', 'urgent', 'critical', 'broken',
            'fuite', 'incendie', 'gaz', 'sécurité', 'urgence', 'danger',
            'حريق', 'غاز', 'أمان', 'طوارئ', 'خطر', 'تسرب'
        ]
        
        combined_text = f"{self.title} {self.description}".lower()
        
        if any(keyword in combined_text for keyword in urgent_keywords):
            self.is_urgent_auto_detected = True
            if self.priority == self.Priority.LOW or self.priority == self.Priority.MEDIUM:
                self.priority = self.Priority.HIGH
    
    def _calculate_sla(self):
        """Calculate SLA due date based on priority."""
        if not self.sla_due_date:
            sla_hours = {
                self.Priority.URGENT: 24,
                self.Priority.HIGH: 48,
                self.Priority.MEDIUM: 72,
                self.Priority.LOW: 120,
            }
            hours = sla_hours.get(self.priority, 72)
            self.sla_due_date = timezone.now() + timezone.timedelta(hours=hours)
    
    def get_response_time(self):
        """Get time since ticket was created or reopened."""
        return timezone.now() - self.created_at
    
    def mark_as_in_progress(self, user=None):
        """Mark ticket as in progress."""
        self.status = self.Status.IN_PROGRESS
        self.assigned_to = user or self.assigned_to
        self.save()
    
    def mark_as_resolved(self, user=None):
        """Mark ticket as resolved."""
        self.status = self.Status.RESOLVED
        self.resolved_at = timezone.now()
        self.save()
    
    def mark_as_closed(self, user=None):
        """Mark ticket as closed."""
        self.status = self.Status.CLOSED
        self.closed_at = timezone.now()
        self.save()
    
    def reopen(self):
        """Reopen a closed/resolved ticket."""
        self.status = self.Status.REOPENED
        self.resolved_at = None
        self.closed_at = None
        self.save()
    
    def get_message_count(self):
        """Get total message count for this ticket."""
        return self.messages.count()
    
    def get_latest_message(self):
        """Get the most recent message."""
        return self.messages.latest('created_at') if self.messages.exists() else None


class TicketMessage(models.Model):
    """
    Chat-style messages within a ticket.
    
    Supports both resident and staff communication.
    Messages can be internal (staff-only) or public (visible to resident).
    """
    
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ticket_messages')
    message = models.TextField()
    is_internal = models.BooleanField(
        default=False,
        help_text="If True, only visible to staff (not to resident)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['ticket', 'created_at']),
            models.Index(fields=['author', 'created_at']),
        ]
    
    def __str__(self):
        return f"Message on {self.ticket.title} by {self.author}"


class TicketAttachment(models.Model):
    """
    File attachments for tickets and messages.
    
    Supports images and documents for evidence/proof.
    """
    
    # Allowed file types
    ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'txt']
    
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='attachments')
    message = models.ForeignKey(
        TicketMessage,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attachments'
    )
    
    file = models.FileField(
        upload_to='tickets/attachments/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS)]
    )
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=50, blank=True)  # e.g., 'image/jpeg', 'application/pdf'
    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ticket_attachments')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['ticket', 'uploaded_at']),
        ]
    
    def __str__(self):
        return self.file_name
    
    def save(self, *args, **kwargs):
        """Store file metadata."""
        if self.file:
            self.file_name = self.file.name
            self.file_size = self.file.size
            self.file_type = self.file.content_type
        super().save(*args, **kwargs)
    
    def get_file_size_display(self):
        """Return human-readable file size."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.file_size < 1024:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024
        return f"{self.file_size:.1f} TB"
    
    def is_image(self):
        """Check if attachment is an image."""
        return self.file_type and self.file_type.startswith('image/')


class TicketSLA(models.Model):
    """
    SLA Configuration for different priority levels.
    
    Defines response times and resolution times for each priority.
    """
    
    priority = models.CharField(
        max_length=20,
        choices=Ticket.Priority.choices,
        unique=True,
        primary_key=True
    )
    response_time_hours = models.IntegerField(default=24, help_text="Time to first response")
    resolution_time_hours = models.IntegerField(default=72, help_text="Time to resolution")
    
    class Meta:
        verbose_name_plural = "Ticket SLAs"
    
    def __str__(self):
        return f"SLA for {self.get_priority_display()} tickets"


class TicketActivityLog(models.Model):
    """Audit trail for ticket changes."""
    
    ACTION_CHOICES = [
        ('created', 'Ticket Created'),
        ('status_changed', 'Status Changed'),
        ('assigned', 'Assigned'),
        ('commented', 'Comment Added'),
        ('attachment_added', 'Attachment Added'),
        ('priority_changed', 'Priority Changed'),
        ('reopened', 'Reopened'),
        ('closed', 'Closed'),
    ]
    
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    old_value = models.CharField(max_length=255, blank=True)
    new_value = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ticket', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.ticket} - {self.action}"
