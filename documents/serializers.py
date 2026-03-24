"""Serialization helpers for document APIs."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DocumentSummarySerializer:
    id: int
    title: str
    amount: float
    resident_name: str
    is_paid: bool

    def to_dict(self):
        return asdict(self)
