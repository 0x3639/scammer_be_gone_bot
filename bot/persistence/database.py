"""SQLite database layer using aiosqlite."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from bot.persistence.models import AlertRecord, ObservedMember, WhitelistEntry

DB_PATH = Path("bot_data.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS observed_members (
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    last_seen TEXT NOT NULL,
    PRIMARY KEY (user_id, chat_id)
);

CREATE TABLE IF NOT EXISTS alert_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    admin_username TEXT NOT NULL,
    similarity_score REAL NOT NULL,
    detection_details TEXT NOT NULL,
    alerted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS whitelist (
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    username TEXT,
    reason TEXT NOT NULL,
    added_at TEXT NOT NULL,
    added_by INTEGER NOT NULL,
    PRIMARY KEY (user_id, chat_id)
);

CREATE INDEX IF NOT EXISTS idx_alert_records_user_chat
    ON alert_records (user_id, chat_id, alerted_at);
"""


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._conn = await aiosqlite.connect(self._db_path)
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        # Migrate: add bio column if it doesn't exist
        try:
            await self._conn.execute("ALTER TABLE observed_members ADD COLUMN bio TEXT")
            await self._conn.commit()
        except aiosqlite.OperationalError:
            pass  # Column already exists

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not initialized — call initialize() first")
        return self._conn

    # --- Observed Members ---

    async def upsert_member(self, member: ObservedMember) -> None:
        await self.conn.execute(
            """
            INSERT INTO observed_members (user_id, chat_id, username, first_name, last_name, last_seen, bio)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id, chat_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                last_seen = excluded.last_seen,
                bio = COALESCE(excluded.bio, observed_members.bio)
            """,
            (
                member.user_id,
                member.chat_id,
                member.username,
                member.first_name,
                member.last_name,
                member.last_seen.isoformat(),
                member.bio,
            ),
        )
        await self.conn.commit()

    async def get_members_by_chat(self, chat_id: int) -> list[ObservedMember]:
        cursor = await self.conn.execute(
            "SELECT user_id, chat_id, username, first_name, last_name, last_seen, bio "
            "FROM observed_members WHERE chat_id = ?",
            (chat_id,),
        )
        rows = await cursor.fetchall()
        return [
            ObservedMember(
                user_id=r[0],
                chat_id=r[1],
                username=r[2],
                first_name=r[3],
                last_name=r[4],
                last_seen=datetime.fromisoformat(r[5]),
                bio=r[6],
            )
            for r in rows
        ]

    async def remove_member(self, user_id: int, chat_id: int) -> None:
        await self.conn.execute(
            "DELETE FROM observed_members WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id),
        )
        await self.conn.commit()

    # --- Alert Records ---

    async def record_alert(self, alert: AlertRecord) -> None:
        await self.conn.execute(
            """
            INSERT INTO alert_records (user_id, chat_id, admin_username, similarity_score, detection_details, alerted_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                alert.user_id,
                alert.chat_id,
                alert.admin_username,
                alert.similarity_score,
                alert.detection_details,
                alert.alerted_at.isoformat(),
            ),
        )
        await self.conn.commit()

    async def get_last_alert_time(
        self, user_id: int, chat_id: int
    ) -> datetime | None:
        cursor = await self.conn.execute(
            "SELECT MAX(alerted_at) FROM alert_records WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id),
        )
        row = await cursor.fetchone()
        if row and row[0]:
            return datetime.fromisoformat(row[0])
        return None

    async def get_recent_alerts(self, chat_id: int, limit: int = 10) -> list[AlertRecord]:
        cursor = await self.conn.execute(
            "SELECT id, user_id, chat_id, admin_username, similarity_score, detection_details, alerted_at "
            "FROM alert_records WHERE chat_id = ? ORDER BY alerted_at DESC LIMIT ?",
            (chat_id, limit),
        )
        rows = await cursor.fetchall()
        return [
            AlertRecord(
                id=r[0],
                user_id=r[1],
                chat_id=r[2],
                admin_username=r[3],
                similarity_score=r[4],
                detection_details=r[5],
                alerted_at=datetime.fromisoformat(r[6]),
            )
            for r in rows
        ]

    async def get_alert_count(self, chat_id: int) -> int:
        cursor = await self.conn.execute(
            "SELECT COUNT(*) FROM alert_records WHERE chat_id = ?",
            (chat_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    # --- Whitelist ---

    async def add_whitelist(self, entry: WhitelistEntry) -> None:
        await self.conn.execute(
            """
            INSERT INTO whitelist (user_id, chat_id, username, reason, added_at, added_by)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id, chat_id) DO UPDATE SET
                username = excluded.username,
                reason = excluded.reason,
                added_at = excluded.added_at,
                added_by = excluded.added_by
            """,
            (
                entry.user_id,
                entry.chat_id,
                entry.username,
                entry.reason,
                entry.added_at.isoformat(),
                entry.added_by,
            ),
        )
        await self.conn.commit()

    async def remove_whitelist(self, user_id: int, chat_id: int) -> None:
        await self.conn.execute(
            "DELETE FROM whitelist WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id),
        )
        await self.conn.commit()

    async def is_whitelisted(self, user_id: int, chat_id: int) -> bool:
        cursor = await self.conn.execute(
            "SELECT 1 FROM whitelist WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id),
        )
        return await cursor.fetchone() is not None

    async def get_whitelist(self, chat_id: int) -> list[WhitelistEntry]:
        cursor = await self.conn.execute(
            "SELECT user_id, chat_id, username, reason, added_at, added_by "
            "FROM whitelist WHERE chat_id = ?",
            (chat_id,),
        )
        rows = await cursor.fetchall()
        return [
            WhitelistEntry(
                user_id=r[0],
                chat_id=r[1],
                username=r[2],
                reason=r[3],
                added_at=datetime.fromisoformat(r[4]),
                added_by=r[5],
            )
            for r in rows
        ]

    # --- Stats ---

    async def get_member_count(self, chat_id: int) -> int:
        cursor = await self.conn.execute(
            "SELECT COUNT(*) FROM observed_members WHERE chat_id = ?",
            (chat_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
