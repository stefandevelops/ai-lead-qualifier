from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from lead_qualifier.models import Qualification

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    email TEXT NOT NULL UNIQUE,
    title TEXT,
    company TEXT,
    industry TEXT,
    employees INTEGER,
    country TEXT,
    source TEXT,
    notes TEXT,
    domain TEXT,
    seniority TEXT,
    seniority_label TEXT,
    size_band TEXT,
    region TEXT,
    geo_fit TEXT,
    industry_norm TEXT,
    industry_fit TEXT,
    persona TEXT,
    intent_level TEXT,
    signals TEXT,
    score INTEGER,
    tier TEXT,
    explanation TEXT,
    email_subject TEXT,
    email_body TEXT,
    draft_engine TEXT,
    status TEXT
);
"""

COLUMNS = [
    "id",
    "created_at",
    "updated_at",
    "first_name",
    "last_name",
    "email",
    "title",
    "company",
    "industry",
    "employees",
    "country",
    "source",
    "notes",
    "domain",
    "seniority",
    "seniority_label",
    "size_band",
    "region",
    "geo_fit",
    "industry_norm",
    "industry_fit",
    "persona",
    "intent_level",
    "signals",
    "score",
    "tier",
    "explanation",
    "email_subject",
    "email_body",
    "draft_engine",
    "status",
]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class CRM:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM leads").fetchone()
        return int(row["n"])

    def upsert(self, qualification: Qualification) -> int:
        record = qualification.to_record()
        now = _now()
        existing = self.get_by_email(record["email"])
        if existing:
            return self._update_existing(existing["id"], record, now)
        keys = [col for col in COLUMNS if col != "id"]
        payload = {col: record.get(col) for col in keys}
        payload["created_at"] = now
        payload["updated_at"] = now
        sql = f"INSERT INTO leads ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)})"
        cursor = self._conn.execute(sql, [payload[k] for k in keys])
        self._conn.commit()
        return int(cursor.lastrowid)

    def _update_existing(self, lead_id: int, record: dict, now: str) -> int:
        keys = [col for col in COLUMNS if col not in {"id", "created_at"}]
        payload = {col: record.get(col) for col in keys}
        payload["updated_at"] = now
        sql = f"UPDATE leads SET {', '.join(f'{k} = ?' for k in keys)} WHERE id = ?"
        self._conn.execute(sql, [payload[k] for k in keys] + [lead_id])
        self._conn.commit()
        return lead_id

    def get_by_email(self, email: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM leads WHERE email = ?", (email.strip(),)).fetchone()
        return dict(row) if row else None

    def get(self, lead_id: int) -> dict | None:
        row = self._conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return dict(row) if row else None

    def list_leads(self, tier: str | None = None) -> list[dict]:
        if tier:
            rows = self._conn.execute(
                "SELECT * FROM leads WHERE tier = ? ORDER BY score DESC, updated_at DESC",
                (tier,),
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM leads ORDER BY score DESC, updated_at DESC").fetchall()
        return [dict(row) for row in rows]

    def update_status(self, lead_id: int, status: str) -> None:
        self._conn.execute(
            "UPDATE leads SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), lead_id),
        )
        self._conn.commit()

    def stats(self) -> dict:
        rows = self.list_leads()
        if not rows:
            return {
                "total": 0,
                "average_score": 0.0,
                "by_tier": {"hot": 0, "warm": 0, "cold": 0},
            }
        scores = [int(row["score"] or 0) for row in rows]
        by_tier = {"hot": 0, "warm": 0, "cold": 0}
        for row in rows:
            tier = row["tier"] or "cold"
            by_tier[tier] = by_tier.get(tier, 0) + 1
        return {
            "total": len(rows),
            "average_score": round(sum(scores) / len(scores), 1),
            "by_tier": by_tier,
        }

    def export_csv(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = self.list_leads()
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({col: row.get(col, "") for col in COLUMNS})
        return path

    def export_csv_text(self) -> str:
        from io import StringIO

        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=COLUMNS)
        writer.writeheader()
        for row in self.list_leads():
            writer.writerow({col: row.get(col, "") for col in COLUMNS})
        return buffer.getvalue()
