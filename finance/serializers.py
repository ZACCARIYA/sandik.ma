"""Serialization helpers for finance APIs."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class NavigationStatsSerializer:
    """Structured payload for dashboard/navigation summary counters."""

    total_residents: int
    total_documents: int
    total_expenses: int
    overdue_count: int
    unread_notifications: int
    issue_reports: int
    documents_this_month: int
    payments_this_month: float
    expenses_this_month: float
    recent_residents: int
    timestamp: str

    def to_dict(self):
        return asdict(self)
