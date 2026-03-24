"""Serialization helpers for residents APIs."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ResidentSummarySerializer:
    id: int
    full_name: str
    apartment: str
    status: str

    def to_dict(self):
        return asdict(self)
