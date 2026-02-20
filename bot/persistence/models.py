"""Data models for persistence layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ObservedMember:
    user_id: int
    chat_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    last_seen: datetime

    @property
    def display_name(self) -> str:
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts) if parts else ""


@dataclass
class AlertRecord:
    id: int | None
    user_id: int
    chat_id: int
    admin_username: str
    similarity_score: float
    detection_details: str
    alerted_at: datetime


@dataclass
class WhitelistEntry:
    user_id: int
    chat_id: int
    username: str | None
    reason: str
    added_at: datetime
    added_by: int
