"""SQLite cache of verified LLM findings, keyed by a hash of the listing text.

Stores only the hash, the verified quotes and a timestamp: never full listing texts.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from app.signals.text_llm import LlmFindings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_findings (
    key TEXT PRIMARY KEY,
    quotes TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


class FindingsCache:
    def __init__(self, path: Path, ttl: timedelta) -> None:
        self._path = path
        self._ttl = ttl
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def get(self, key: str, now: datetime) -> LlmFindings | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT quotes, created_at FROM llm_findings WHERE key = ?", (key,)
            ).fetchone()
        if row is None or now - datetime.fromisoformat(row[1]) > self._ttl:
            return None
        return LlmFindings(quotes=json.loads(row[0]))

    def put(self, key: str, findings: LlmFindings, now: datetime) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO llm_findings (key, quotes, created_at) VALUES (?, ?, ?)",
                (key, json.dumps(findings.quotes, ensure_ascii=False), now.isoformat()),
            )
