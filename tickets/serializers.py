"""
Serializers for Ticket system API and forms.
"""

from dataclasses import dataclass, asdict
from typing import Optional
from decimal import Decimal
from django.contrib.auth import get_user_model

User = get_user_model()


@dataclass(frozen=True)
class TicketListItemSerializer:
    """Lightweight serializer for ticket list views."""
    
    id: int
    title: str
    status: str
    priority: str
    resident_name: str
    assigned_to_name: Optional[str]
    created_at: str
    message_count: int
    
    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class TicketDetailSerializer:
    """Complete serializer for ticket detail view."""
    
    id: int
    title: str
    description: str
    status: str
    priority: str
    category: str
    resident_name: str
    apartment: str
    assigned_to_name: Optional[str]
    created_at: str
    updated_at: str
    resolved_at: Optional[str]
    closed_at: Optional[str]
    sla_due_date: Optional[str]
    sla_breached: bool
    is_urgent_auto_detected: bool
    internal_notes: str
    tags: str
    message_count: int
    attachment_count: int
    
    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class TicketMessageSerializer:
    """Serializer for ticket messages."""
    
    id: int
    author_name: str
    author_avatar: Optional[str]
    message: str
    is_internal: bool
    created_at: str
    updated_at: str
    attachment_count: int
    
    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class DashboardTicketStatsSerializer:
    """Dashboard statistics for tickets."""
    
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    closed_tickets: int
    urgent_tickets: int
    overdue_sla_tickets: int
    avg_response_time_hours: float
    
    def to_dict(self):
        return asdict(self)
