"""Serialization helpers for notifications APIs."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class NotificationSummarySerializer:
    id: int
    title: str
    notification_type: str
    priority: str
    is_read: bool

    def to_dict(self):
        return asdict(self)
