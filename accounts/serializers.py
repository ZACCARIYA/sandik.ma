"""Serialization helpers for account-related APIs."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class UserSummarySerializer:
    """Minimal user summary payload."""

    id: int
    username: str
    role: str
    full_name: str
    email: str
    apartment: str

    def to_dict(self):
        return asdict(self)
