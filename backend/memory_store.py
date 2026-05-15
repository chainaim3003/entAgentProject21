"""
memory_store.py — The Memory Agent's persistence backend.

This is the *only genuinely new build* per DESIGN/DESIGN1/design-1-problem-solution-impact.md §2.
Stores every recommendation with its inputs and predicted outcome. Next cycle compares
predicted-vs-realised and surfaces drift.

Why deterministic, no LLM:
  Storing a record and comparing two numbers doesn't need reasoning.
  Plain SQLite. Backend swappable (Postgres in one line — see comment in compare()).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendations (
    record_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    validated_inputs TEXT NOT NULL,          -- JSON
    simulation_result TEXT NOT NULL,         -- JSON {A_total, B_total, C_total, events}
    recommendation TEXT NOT NULL,            -- JSON {winner, $saving, cost_of_delay, why}
    audit_log TEXT NOT NULL,                 -- JSON list of per-node entries
    realised_at TEXT,                        -- NULL until next cycle
    realised_payload TEXT,                   -- JSON, NULL until next cycle
    drift TEXT                               -- JSON {predicted, realised, delta_$, attribution}
);

CREATE INDEX IF NOT EXISTS idx_recs_thread ON recommendations(thread_id);
CREATE INDEX IF NOT EXISTS idx_recs_created ON recommendations(created_at);
"""


@contextmanager
def _connection():
    """Yield a SQLite connection. Caller responsible for the transaction."""
    conn = sqlite3.connect(settings.memory_db_path)
    try:
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist. Called once at app startup."""
    with _connection() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def save(
    *,
    thread_id: str,
    validated_inputs: dict[str, Any],
    simulation_result: dict[str, Any],
    recommendation: dict[str, Any],
    audit_log: list[dict[str, Any]],
) -> str:
    """Persist a recommendation record. Returns the new record_id."""
    record_id = f"rec-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    with _connection() as conn:
        conn.execute(
            """
            INSERT INTO recommendations (
                record_id, thread_id, created_at,
                validated_inputs, simulation_result, recommendation, audit_log
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                thread_id,
                now,
                json.dumps(validated_inputs, default=str),
                json.dumps(simulation_result, default=str),
                json.dumps(recommendation, default=str),
                json.dumps(audit_log, default=str),
            ),
        )
        conn.commit()
    return record_id


def compare(record_id: str, realised: dict[str, Any]) -> dict[str, Any]:
    """Compare a prior recommendation's predicted outcome vs realised numbers.

    Stores the drift back on the record. Returns the drift payload.

    Drift attribution is left to the caller (a future analytics step) — this function
    captures the raw delta. Because the knot is deterministic, drift attributes cleanly
    to the wings, not the core.

    Args:
        record_id: the recommendation to compare against
        realised: {"realised_total": float, "as_of": iso8601 str, ...} — caller-defined
    """
    with _connection() as conn:
        row = conn.execute(
            "SELECT recommendation FROM recommendations WHERE record_id = ?",
            (record_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"No recommendation with record_id={record_id}")

        recommendation = json.loads(row["recommendation"])
        predicted_saving = recommendation.get("predicted_saving")
        realised_saving = realised.get("realised_saving")

        if predicted_saving is None or realised_saving is None:
            raise ValueError(
                "Cannot compute drift: need predicted_saving in stored recommendation "
                "AND realised_saving in `realised` payload."
            )

        drift = {
            "predicted_saving": predicted_saving,
            "realised_saving": realised_saving,
            "delta_usd": realised_saving - predicted_saving,
            "as_of": realised.get("as_of"),
        }

        conn.execute(
            """
            UPDATE recommendations
            SET realised_at = ?, realised_payload = ?, drift = ?
            WHERE record_id = ?
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                json.dumps(realised, default=str),
                json.dumps(drift, default=str),
                record_id,
            ),
        )
        conn.commit()

    return drift


def list_history(*, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """Return recent recommendations + drift, newest first."""
    with _connection() as conn:
        rows = conn.execute(
            """
            SELECT record_id, thread_id, created_at, recommendation, drift
            FROM recommendations
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

    return [
        {
            "record_id": r["record_id"],
            "thread_id": r["thread_id"],
            "created_at": r["created_at"],
            "recommendation": json.loads(r["recommendation"]),
            "drift": json.loads(r["drift"]) if r["drift"] else None,
        }
        for r in rows
    ]
