"""
Django Admin configuration for Tickets app.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from .models import (
    Ticket, TicketMessage, TicketAttachment, TicketCategory,
    TicketSLA, TicketActivityLog
)


@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    """Admin for Ticket Categories."""
    
    list_display = ('name_en', 'name_fr', 'is_active', 'ticket_count')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name_en', 'name_fr')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name_en', 'name_fr', 'name_ar', 'icon')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def ticket_count(self, obj):
        """Show number of tickets in this category."""
        count = obj.tickets.count()
        return format_html(
            '<span style="background-color: #007bff; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            count
        )
    ticket_count.short_description = 'Tickets'


class TicketMessageInline(admin.TabularInline):
    """Inline messages for ticket admin."""
    
    model = TicketMessage
    extra = 0
    fields = ('author', 'message', 'is_internal', 'created_at')
    readonly_fields = ('author', 'created_at')
    can_delete = False


class TicketAttachmentInline(admin.TabularInline):
    """Inline attachments for ticket admin."""
    
    model = TicketAttachment
    extra = 0
    fields = ('file_name', 'uploaded_by', 'uploaded_at', 'file_size')
    readonly_fields = ('file_name', 'uploaded_by', 'uploaded_at', 'file_size')
    can_delete = False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    """Admin for Tickets."""
    
    list_display = (
        'ticket_id',
        'title_display',
        'resident_display',
        'priority_badge',
        'status_badge',
        'assigned_display',
        'message_count_display',
        'created_at_short'
    )
    list_filter = (
        'status',
        'priority',
        'category',
        'sla_breached',
        'is_urgent_auto_detected',
        'created_at'
    )
    search_fields = ('title', 'description', 'apartment', 'resident__username')
    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
        'resolved_at',
        'closed_at',
        'apartment',
        'sla_due_date',
    )
    
    fieldsets = (
        ('Ticket Info', {
            'fields': ('id', 'title', 'description', 'category')
        }),
        ('Priority & Status', {
            'fields': ('status', 'priority', 'is_urgent_auto_detected')
        }),
        ('Assignment', {
            'fields': ('resident', 'apartment', 'assigned_to')
        }),
        ('SLA', {
            'fields': ('sla_due_date', 'sla_breached')
        }),
        ('Metadata', {
            'fields': ('tags', 'internal_notes', 'created_by'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'resolved_at', 'closed_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [TicketMessageInline, TicketAttachmentInline]
    
    actions = [
        'mark_as_in_progress',
        'mark_as_resolved',
        'mark_as_closed',
        'escalate_to_urgent',
    ]
    
    def ticket_id(self, obj):
        """Display ticket ID with link."""
        return format_html(
            '<a href="{}">#{}</a>',
            reverse('admin:tickets_ticket_change', args=[obj.pk]),
            obj.id
        )
    ticket_id.short_description = 'ID'
    
    def title_display(self, obj):
        """Truncate title."""
        title = obj.title
        return title[:50] + '...' if len(title) > 50 else title
    title_display.short_description = 'Title'
    
    def resident_display(self, obj):
        """Display resident name."""
        return obj.resident.get_full_name() or obj.resident.username
    resident_display.short_description = 'Resident'
    
    def priority_badge(self, obj):
        """Display priority as colored badge."""
        colors = {
            'urgent': '#dc3545',
            'high': '#fd7e14',
            'medium': '#ffc107',
            'low': '#28a745',
        }
        color = colors.get(obj.priority, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'open': '#dc3545',
            'in_progress': '#0dcaf0',
            'resolved': '#198754',
            'closed': '#6c757d',
            'reopened': '#0d6efd',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def assigned_display(self, obj):
        """Display assigned admin."""
        if obj.assigned_to:
            return obj.assigned_to.get_full_name() or obj.assigned_to.username
        return format_html('<span style="color: #999;">Unassigned</span>')
    assigned_display.short_description = 'Assigned To'
    
    def message_count_display(self, obj):
        """Display message count."""
        count = obj.messages.count()
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 8px; border-radius: 3px;">{} msg</span>',
            count
        )
    message_count_display.short_description = 'Messages'
    
    def created_at_short(self, obj):
        """Display created date in short format."""
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    created_at_short.short_description = 'Created'
    
    def mark_as_in_progress(self, request, queryset):
        """Mark selected tickets as in progress."""
        updated = queryset.update(status=Ticket.Status.IN_PROGRESS)
        self.message_user(request, f'{updated} ticket(s) marked as in progress.')
    mark_as_in_progress.short_description = 'Mark as In Progress'
    
    def mark_as_resolved(self, request, queryset):
        """Mark selected tickets as resolved."""
        from django.utils import timezone
        updated = queryset.update(
            status=Ticket.Status.RESOLVED,
            resolved_at=timezone.now()
        )
        self.message_user(request, f'{updated} ticket(s) marked as resolved.')
    mark_as_resolved.short_description = 'Mark as Resolved'
    
    def mark_as_closed(self, request, queryset):
        """Mark selected tickets as closed."""
        from django.utils import timezone
        updated = queryset.update(
            status=Ticket.Status.CLOSED,
            closed_at=timezone.now()
        )
        self.message_user(request, f'{updated} ticket(s) marked as closed.')
    mark_as_closed.short_description = 'Mark as Closed'
    
    def escalate_to_urgent(self, request, queryset):
        """Escalate tickets to urgent priority."""
        updated = queryset.update(priority=Ticket.Priority.URGENT)
        self.message_user(request, f'{updated} ticket(s) escalated to urgent.')
    escalate_to_urgent.short_description = '🔴 Escalate to Urgent'


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    """Admin for Ticket Messages."""
    
    list_display = ('ticket_display', 'author_display', 'message_preview', 'is_internal_badge', 'created_at')
    list_filter = ('is_internal', 'created_at', 'author__role')
    search_fields = ('ticket__title', 'author__username', 'message')
    readonly_fields = ('ticket', 'author', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Message Info', {
            'fields': ('ticket', 'author', 'message')
        }),
        ('Settings', {
            'fields': ('is_internal',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def ticket_display(self, obj):
        """Display ticket link."""
        return format_html(
            '<a href="{}">#{} - {}</a>',
            reverse('admin:tickets_ticket_change', args=[obj.ticket.pk]),
            obj.ticket.id,
            obj.ticket.title[:30]
        )
    ticket_display.short_description = 'Ticket'
    
    def author_display(self, obj):
        """Display author name with role."""
        return f"{obj.author.get_full_name()} ({obj.author.get_role_display()})"
    author_display.short_description = 'Author'
    
    def message_preview(self, obj):
        """Display message preview."""
        preview = obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
        return preview
    message_preview.short_description = 'Message'
    
    def is_internal_badge(self, obj):
        """Display internal flag as badge."""
        if obj.is_internal:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 6px; border-radius: 3px;">Internal</span>'
            )
        return format_html(
            '<span style="background-color: #28a745; color: white; padding: 3px 6px; border-radius: 3px;">Public</span>'
        )
    is_internal_badge.short_description = 'Visibility'


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    """Admin for Ticket Attachments."""
    
    list_display = ('ticket_display', 'file_name', 'file_size_display', 'uploaded_by_display', 'uploaded_at')
    list_filter = ('uploaded_at', 'file_type')
    search_fields = ('ticket__title', 'file_name', 'uploaded_by__username')
    readonly_fields = ('ticket', 'message', 'file', 'uploaded_by', 'uploaded_at')
    
    def ticket_display(self, obj):
        """Display ticket link."""
        return format_html(
            '<a href="{}">#{}</a>',
            reverse('admin:tickets_ticket_change', args=[obj.ticket.pk]),
            obj.ticket.id
        )
    ticket_display.short_description = 'Ticket'
    
    def file_size_display(self, obj):
        """Display file size in human-readable format."""
        return obj.get_file_size_display()
    file_size_display.short_description = 'Size'
    
    def uploaded_by_display(self, obj):
        """Display uploader name."""
        return obj.uploaded_by.get_full_name() or obj.uploaded_by.username
    uploaded_by_display.short_description = 'Uploaded By'


@admin.register(TicketActivityLog)
class TicketActivityLogAdmin(admin.ModelAdmin):
    """Admin for Ticket Activity Logs."""
    
    list_display = ('ticket_display', 'action', 'performed_by_display', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('ticket__title', 'performed_by__username')
    readonly_fields = ('ticket', 'performed_by', 'created_at')
    
    fieldsets = (
        ('Action Info', {
            'fields': ('ticket', 'action', 'performed_by')
        }),
        ('Details', {
            'fields': ('old_value', 'new_value', 'description')
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def ticket_display(self, obj):
        """Display ticket link."""
        return format_html(
            '<a href="{}">#{}</a>',
            reverse('admin:tickets_ticket_change', args=[obj.ticket.pk]),
            obj.ticket.id
        )
    ticket_display.short_description = 'Ticket'
    
    def performed_by_display(self, obj):
        """Display performer name."""
        return obj.performed_by.get_full_name() or obj.performed_by.username
    performed_by_display.short_description = 'Performed By'


admin.site.site_header = "Snadik.ma - Ticket Management"
admin.site.site_title = "Ticket Admin"
