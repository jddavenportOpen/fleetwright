"""
fleetwright/fleet/checkpoints.py — durable agent run state with pluggable DB backends.

Supports three backends (set via DB_BACKEND env var):
  - sqlite  (default) — zero-dependency local dev; no server needed
  - postgres          — via psycopg2; set DATABASE_URL
  - supabase          — via supabase-py; set SUPABASE_URL + SUPABASE_SERVICE_KEY

Public API:
  - create_run(run_id, agent, objective, parent_run_id=None) → run_id
  - update_status(run_id, status) → None
  - checkpoint(run_id, step, state) → None
  - resume(run_id) → tuple[int, dict]
  - list_active(parent_run_id=None) → list[Run]
  - record_cost(run_id, tokens_in, tokens_out, cost_usd) → None
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

log = logging.getLogger(__name__)

VALID_STATUSES = frozenset({
    "planning", "awaiting-approval", "running",
    "done", "failed", "cancelled",
})


# ── Run model ─────────────────────────────────────────────────────────────────
@dataclass
class Run:
    run_id: str
    agent: str
    objective: str
    status: str
    parent_run_id: Optional[str] = None
    checkpoint_json: Dict[str, Any] = field(default_factory=dict)
    cost_usd_total: float = 0.0
    tokens_input: int = 0
    tokens_output: int = 0
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    error: Optional[str] = None


# ── Adapter protocol ──────────────────────────────────────────────────────────
@runtime_checkable
class DBAdapter(Protocol):
    def create_run(
        self, run_id: str, agent: str, objective: str, parent_run_id: Optional[str] = None
    ) -> str: ...

    def update_status(self, run_id: str, status: str) -> None: ...

    def checkpoint(self, run_id: str, step: int, state: Dict[str, Any]) -> None: ...

    def resume(self, run_id: str) -> tuple[int, Dict[str, Any]]: ...

    def list_active(self, parent_run_id: Optional[str] = None) -> List[Run]: ...

    def record_cost(
        self, run_id: str, tokens_in: int, tokens_out: int, cost_usd: float
    ) -> None: ...

    def fetch_row(self, run_id: str) -> Optional[Dict[str, Any]]: ...


# ── SQLite adapter (default) ──────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_runs (
    run_id          TEXT PRIMARY KEY,
    agent           TEXT NOT NULL,
    objective       TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'planning',
    parent_run_id   TEXT,
    checkpoint_json TEXT NOT NULL DEFAULT '{}',
    cost_usd_total  REAL NOT NULL DEFAULT 0.0,
    tokens_input    INTEGER NOT NULL DEFAULT 0,
    tokens_output   INTEGER NOT NULL DEFAULT 0,
    started_at      TEXT,
    updated_at      TEXT,
    error           TEXT
);
"""


class SQLiteAdapter:
    """SQLite-backed checkpoint store. Zero external dependencies."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        # Create schema
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        if not getattr(self._local, "conn", None):
            self._local.conn = sqlite3.connect(str(self._path), check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_run(
        self, run_id: str, agent: str, objective: str, parent_run_id: Optional[str] = None
    ) -> str:
        now = self._now()
        try:
            with self._conn() as conn:
                conn.execute(
                    """INSERT OR IGNORE INTO agent_runs
                       (run_id, agent, objective, status, parent_run_id, started_at, updated_at)
                       VALUES (?, ?, ?, 'planning', ?, ?, ?)""",
                    (run_id, agent, objective, parent_run_id, now, now),
                )
        except Exception as e:
            log.warning("create_run failed: %s", e)
        return run_id

    def update_status(self, run_id: str, status: str) -> None:
        if status not in VALID_STATUSES:
            log.warning("invalid status %r for run %s", status, run_id)
            return
        try:
            with self._conn() as conn:
                conn.execute(
                    "UPDATE agent_runs SET status=?, updated_at=? WHERE run_id=?",
                    (status, self._now(), run_id),
                )
        except Exception as e:
            log.warning("update_status failed: %s", e)

    def checkpoint(self, run_id: str, step: int, state: Dict[str, Any]) -> None:
        try:
            row = self.fetch_row(run_id)
            existing = json.loads(row.get("checkpoint_json", "{}") if row else "{}")
            existing[str(step)] = state
            with self._conn() as conn:
                conn.execute(
                    "UPDATE agent_runs SET checkpoint_json=?, updated_at=? WHERE run_id=?",
                    (json.dumps(existing), self._now(), run_id),
                )
        except Exception as e:
            log.warning("checkpoint failed: %s", e)

    def resume(self, run_id: str) -> tuple[int, Dict[str, Any]]:
        try:
            row = self.fetch_row(run_id)
            if not row:
                return 0, {}
            data = json.loads(row.get("checkpoint_json", "{}") or "{}")
            if not data:
                return 0, {}
            last_step = max(int(k) for k in data)
            return last_step, data[str(last_step)]
        except Exception as e:
            log.warning("resume failed: %s", e)
            return 0, {}

    def list_active(self, parent_run_id: Optional[str] = None) -> List[Run]:
        try:
            with self._conn() as conn:
                if parent_run_id:
                    rows = conn.execute(
                        "SELECT * FROM agent_runs WHERE status NOT IN ('done','failed','cancelled') AND parent_run_id=?",
                        (parent_run_id,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM agent_runs WHERE status NOT IN ('done','failed','cancelled')"
                    ).fetchall()
                return [_row_to_run(dict(r)) for r in rows]
        except Exception as e:
            log.warning("list_active failed: %s", e)
            return []

    def record_cost(
        self, run_id: str, tokens_in: int, tokens_out: int, cost_usd: float
    ) -> None:
        try:
            with self._conn() as conn:
                conn.execute(
                    """UPDATE agent_runs SET
                       tokens_input=tokens_input+?,
                       tokens_output=tokens_output+?,
                       cost_usd_total=cost_usd_total+?,
                       updated_at=?
                       WHERE run_id=?""",
                    (tokens_in, tokens_out, cost_usd, self._now(), run_id),
                )
        except Exception as e:
            log.warning("record_cost failed: %s", e)

    def fetch_row(self, run_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM agent_runs WHERE run_id=?", (run_id,)
                ).fetchone()
                return dict(row) if row else None
        except Exception as e:
            log.warning("fetch_row failed: %s", e)
            return None


# ── Supabase adapter ──────────────────────────────────────────────────────────
class SupabaseAdapter:
    """Supabase-backed checkpoint store via direct HTTP (no supabase-py dep required)."""

    _TABLE = "agent_runs"
    _TIMEOUT = 5.0

    def __init__(self, url: str, service_key: str) -> None:
        self._url = url.rstrip("/")
        self._key = service_key
        try:
            import httpx
            self._client = httpx.Client(
                base_url=f"{self._url}/rest/v1",
                headers={
                    "apikey": self._key,
                    "Authorization": f"Bearer {self._key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation",
                },
                timeout=self._TIMEOUT,
            )
        except ImportError:
            raise RuntimeError("httpx is required for the Supabase adapter; `pip install httpx`")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _get(self, run_id: str) -> Optional[Dict[str, Any]]:
        try:
            r = self._client.get(f"/{self._TABLE}", params={"run_id": f"eq.{run_id}", "limit": "1"})
            r.raise_for_status()
            rows = r.json()
            return rows[0] if rows else None
        except Exception as e:
            log.warning("supabase get failed: %s", e)
            return None

    def create_run(self, run_id: str, agent: str, objective: str, parent_run_id: Optional[str] = None) -> str:
        now = self._now()
        try:
            self._client.post(
                f"/{self._TABLE}",
                json={
                    "run_id": run_id, "agent": agent, "objective": objective,
                    "status": "planning", "parent_run_id": parent_run_id,
                    "started_at": now, "updated_at": now,
                },
                headers={"Prefer": "resolution=ignore-duplicates,return=minimal"},
            ).raise_for_status()
        except Exception as e:
            log.warning("create_run failed: %s", e)
        return run_id

    def update_status(self, run_id: str, status: str) -> None:
        try:
            self._client.patch(
                f"/{self._TABLE}", params={"run_id": f"eq.{run_id}"},
                json={"status": status, "updated_at": self._now()},
            ).raise_for_status()
        except Exception as e:
            log.warning("update_status failed: %s", e)

    def checkpoint(self, run_id: str, step: int, state: Dict[str, Any]) -> None:
        row = self._get(run_id)
        existing = json.loads(row.get("checkpoint_json", "{}") if row else "{}")
        existing[str(step)] = state
        try:
            self._client.patch(
                f"/{self._TABLE}", params={"run_id": f"eq.{run_id}"},
                json={"checkpoint_json": json.dumps(existing), "updated_at": self._now()},
            ).raise_for_status()
        except Exception as e:
            log.warning("checkpoint failed: %s", e)

    def resume(self, run_id: str) -> tuple[int, Dict[str, Any]]:
        row = self._get(run_id)
        if not row:
            return 0, {}
        data = json.loads(row.get("checkpoint_json", "{}") or "{}")
        if not data:
            return 0, {}
        last_step = max(int(k) for k in data)
        return last_step, data[str(last_step)]

    def list_active(self, parent_run_id: Optional[str] = None) -> List[Run]:
        try:
            params = {"status": "not.in.(done,failed,cancelled)", "limit": "500"}
            if parent_run_id:
                params["parent_run_id"] = f"eq.{parent_run_id}"
            r = self._client.get(f"/{self._TABLE}", params=params)
            r.raise_for_status()
            return [_row_to_run(row) for row in r.json()]
        except Exception as e:
            log.warning("list_active failed: %s", e)
            return []

    def record_cost(self, run_id: str, tokens_in: int, tokens_out: int, cost_usd: float) -> None:
        row = self._get(run_id)
        if not row:
            return
        try:
            self._client.patch(
                f"/{self._TABLE}", params={"run_id": f"eq.{run_id}"},
                json={
                    "tokens_input": (row.get("tokens_input") or 0) + tokens_in,
                    "tokens_output": (row.get("tokens_output") or 0) + tokens_out,
                    "cost_usd_total": (row.get("cost_usd_total") or 0.0) + cost_usd,
                    "updated_at": self._now(),
                },
            ).raise_for_status()
        except Exception as e:
            log.warning("record_cost failed: %s", e)

    def fetch_row(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self._get(run_id)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _row_to_run(row: Dict[str, Any]) -> Run:
    return Run(
        run_id=row.get("run_id", ""),
        agent=row.get("agent", ""),
        objective=row.get("objective", ""),
        status=row.get("status", "planning"),
        parent_run_id=row.get("parent_run_id"),
        checkpoint_json=json.loads(row.get("checkpoint_json") or "{}"),
        cost_usd_total=float(row.get("cost_usd_total") or 0.0),
        tokens_input=int(row.get("tokens_input") or 0),
        tokens_output=int(row.get("tokens_output") or 0),
        started_at=row.get("started_at"),
        updated_at=row.get("updated_at"),
        error=row.get("error"),
    )


# ── Singleton adapter ─────────────────────────────────────────────────────────
_adapter: Optional[DBAdapter] = None
_adapter_lock = threading.Lock()


def _get_adapter() -> DBAdapter:
    global _adapter
    if _adapter is not None:
        return _adapter
    with _adapter_lock:
        if _adapter is not None:
            return _adapter
        from fleetwright import config as _cfg
        backend = _cfg.DB_BACKEND
        if backend == "supabase":
            if not (_cfg.SUPABASE_URL and _cfg.SUPABASE_SERVICE_KEY):
                log.warning(
                    "DB_BACKEND=supabase but SUPABASE_URL/SUPABASE_SERVICE_KEY not set; "
                    "falling back to sqlite"
                )
                _adapter = SQLiteAdapter(_cfg.SQLITE_PATH)
            else:
                _adapter = SupabaseAdapter(_cfg.SUPABASE_URL, _cfg.SUPABASE_SERVICE_KEY)
        elif backend == "postgres":
            try:
                from fleetwright.fleet._pg_adapter import PostgresAdapter
                _adapter = PostgresAdapter(_cfg.DATABASE_URL)
            except ImportError:
                log.warning("psycopg2 not installed; falling back to sqlite")
                _adapter = SQLiteAdapter(_cfg.SQLITE_PATH)
        else:
            _adapter = SQLiteAdapter(_cfg.SQLITE_PATH)
        return _adapter


# ── Public API ────────────────────────────────────────────────────────────────
def create_run(
    run_id: str,
    agent: str,
    objective: str,
    parent_run_id: Optional[str] = None,
) -> str:
    return _get_adapter().create_run(run_id, agent, objective, parent_run_id)


def update_status(run_id: str, status: str) -> None:
    return _get_adapter().update_status(run_id, status)


def checkpoint(run_id: str, step: int, state: Dict[str, Any]) -> None:
    return _get_adapter().checkpoint(run_id, step, state)


def resume(run_id: str) -> tuple[int, Dict[str, Any]]:
    return _get_adapter().resume(run_id)


def list_active(parent_run_id: Optional[str] = None) -> List[Run]:
    return _get_adapter().list_active(parent_run_id)


def record_cost(
    run_id: str, tokens_in: int, tokens_out: int, cost_usd: float
) -> None:
    return _get_adapter().record_cost(run_id, tokens_in, tokens_out, cost_usd)


def _fetch_row(run_id: str) -> Optional[Dict[str, Any]]:
    return _get_adapter().fetch_row(run_id)


def reset_adapter(new_adapter: Optional[DBAdapter] = None) -> None:
    """Replace the singleton adapter. Used in tests."""
    global _adapter
    _adapter = new_adapter
