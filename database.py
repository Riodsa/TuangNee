import os
import sqlite3
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

THAI_MONTHS_SHORT = [
    "",
    "ม.ค.",
    "ก.พ.",
    "มี.ค.",
    "เม.ย.",
    "พ.ค.",
    "มิ.ย.",
    "ก.ค.",
    "ส.ค.",
    "ก.ย.",
    "ต.ค.",
    "พ.ย.",
    "ธ.ค.",
]


def get_current_year_month(tz_name: str = "Asia/Bangkok") -> str:
    """Return current year-month in YYYY-MM format."""
    now = datetime.now(ZoneInfo(tz_name))
    return now.strftime("%Y-%m")


def parse_year_month(value: str) -> str:
    """Validate and normalize a YYYY-MM string (supports CE or BE years >= 2500)."""
    value = value.strip()
    parts = value.split("-")
    if len(parts) != 2:
        raise ValueError("รูปแบบเดือนไม่ถูกต้อง กรุณาใช้ YYYY-MM เช่น 2026-11")
    year = int(parts[0])
    month = int(parts[1])
    if year >= 2400:
        year -= 543  # Convert Buddhist Era (พ.ศ.) to Christian Era (ค.ศ.) if entered
    if not (2000 <= year <= 2100) or not (1 <= month <= 12):
        raise ValueError("ปีหรือเดือนไม่ถูกต้อง กรุณาใช้ YYYY-MM เช่น 2026-11")
    return f"{year:04d}-{month:02d}"


def add_months(ym: str, months_to_add: int) -> str:
    """Add or subtract months from a YYYY-MM string."""
    year, month = map(int, ym.split("-"))
    total_months = (year * 12 + (month - 1)) + months_to_add
    new_year = total_months // 12
    new_month = (total_months % 12) + 1
    return f"{new_year:04d}-{new_month:02d}"


def diff_months(paid_until: str, current_ym: str) -> int:
    """Return (paid_until - current_ym) in months.
    >= 0 means paid up to or ahead of current_ym.
    < 0 means overdue by abs(diff) months.
    """
    y1, m1 = map(int, paid_until.split("-"))
    y2, m2 = map(int, current_ym.split("-"))
    return (y1 * 12 + m1) - (y2 * 12 + m2)


def format_thai_year_month(ym: str) -> str:
    """Format YYYY-MM into Thai readable string, e.g., 'พ.ย. 2569 (2026-11)'."""
    year, month = map(int, ym.split("-"))
    thai_year = year + 543
    month_name = THAI_MONTHS_SHORT[month]
    return f"{month_name} {thai_year} ({ym})"


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("DB_PATH", "icloud_bot.db")
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS groups (
                    group_id TEXT PRIMARY KEY,
                    schedule_day INTEGER NOT NULL DEFAULT 1,
                    schedule_hour INTEGER NOT NULL DEFAULT 9,
                    schedule_minute INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    line_user_id TEXT,
                    paid_until TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(group_id, name COLLATE NOCASE)
                )
                """
            )
            conn.commit()

    def ensure_group(
        self,
        group_id: str,
        default_day: int = 1,
        default_hour: int = 9,
        default_minute: int = 0,
    ) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM groups WHERE group_id = ?", (group_id,)
            ).fetchone()
            if not row:
                now = datetime.utcnow().isoformat()
                conn.execute(
                    """
                    INSERT INTO groups (group_id, schedule_day, schedule_hour, schedule_minute, active, created_at)
                    VALUES (?, ?, ?, ?, 1, ?)
                    """,
                    (group_id, default_day, default_hour, default_minute, now),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM groups WHERE group_id = ?", (group_id,)
                ).fetchone()
            elif row["active"] == 0:
                conn.execute(
                    "UPDATE groups SET active = 1 WHERE group_id = ?", (group_id,)
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM groups WHERE group_id = ?", (group_id,)
                ).fetchone()
            return dict(row)

    def deactivate_group(self, group_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE groups SET active = 0 WHERE group_id = ?", (group_id,)
            )
            conn.commit()

    def get_active_groups(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM groups WHERE active = 1"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_group(self, group_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM groups WHERE group_id = ?", (group_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_group_schedule(
        self, group_id: str, day: int, hour: int, minute: int
    ) -> dict:
        self.ensure_group(group_id)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE groups
                SET schedule_day = ?, schedule_hour = ?, schedule_minute = ?
                WHERE group_id = ?
                """,
                (day, hour, minute, group_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM groups WHERE group_id = ?", (group_id,)
            ).fetchone()
            return dict(row)

    def get_member(self, group_id: str, name: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM members WHERE group_id = ? AND name = ? COLLATE NOCASE",
                (group_id, name.strip()),
            ).fetchone()
            return dict(row) if row else None

    def get_member_by_user_id(
        self, group_id: str, line_user_id: str
    ) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM members WHERE group_id = ? AND line_user_id = ?",
                (group_id, line_user_id),
            ).fetchone()
            return dict(row) if row else None

    def list_members(self, group_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM members WHERE group_id = ? ORDER BY id ASC",
                (group_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def set_member_paid_until(
        self,
        group_id: str,
        name: str,
        paid_until: str,
        line_user_id: Optional[str] = None,
    ) -> dict:
        self.ensure_group(group_id)
        normalized_ym = parse_year_month(paid_until)
        clean_name = name.strip().lstrip("@")
        now = datetime.utcnow().isoformat()

        existing = self.get_member(group_id, clean_name)
        with self._connect() as conn:
            if existing:
                user_id = line_user_id or existing["line_user_id"]
                conn.execute(
                    """
                    UPDATE members
                    SET paid_until = ?, line_user_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (normalized_ym, user_id, now, existing["id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO members (group_id, name, line_user_id, paid_until, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (group_id, clean_name, line_user_id, normalized_ym, now),
                )
            conn.commit()
        return self.get_member(group_id, clean_name)  # type: ignore

    def add_member_paid_months(
        self,
        group_id: str,
        name: str,
        months: int = 1,
        current_ym: Optional[str] = None,
        line_user_id: Optional[str] = None,
    ) -> dict:
        self.ensure_group(group_id)
        clean_name = name.strip().lstrip("@")
        existing = self.get_member(group_id, clean_name)
        if existing:
            new_ym = add_months(existing["paid_until"], months)
            return self.set_member_paid_until(
                group_id, clean_name, new_ym, line_user_id=line_user_id
            )
        else:
            base_ym = current_ym or get_current_year_month()
            # If adding a new member with +1, starting from previous month + months = current_ym
            start_ym = add_months(base_ym, months - 1)
            return self.set_member_paid_until(
                group_id, clean_name, start_ym, line_user_id=line_user_id
            )

    def remove_member(self, group_id: str, name: str) -> bool:
        clean_name = name.strip().lstrip("@")
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM members WHERE group_id = ? AND name = ? COLLATE NOCASE",
                (group_id, clean_name),
            )
            conn.commit()
            return cursor.rowcount > 0

    def clear_members(self, group_id: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM members WHERE group_id = ?",
                (group_id,),
            )
            conn.commit()
            return cursor.rowcount

    def reset_all_members_paid_until(self, group_id: str, paid_until: str) -> int:
        normalized_ym = parse_year_month(paid_until)
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE members
                SET paid_until = ?, updated_at = ?
                WHERE group_id = ?
                """,
                (normalized_ym, now, group_id),
            )
            conn.commit()
            return cursor.rowcount
