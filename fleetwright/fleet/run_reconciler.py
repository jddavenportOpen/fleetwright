#!/usr/bin/env python3
"""
fleetwright/fleet/run_reconciler.py — close the lifecycle of fleet runs
whose process is gone but whose agent_runs row is still non-terminal.

Reconcile loop:
  1. checkpoints.list_active() → every non-terminal run.
  2. For each: is its tmux session alive? If yes → leave it.
  3. If session is gone AND older than GRACE_SEC:
       a. If a .events.jsonl exists, ingest it (idempotent; captures cost + status).
       b. If the run is still non-terminal after ingest, force update_status(done).

CLI:
    python3 -m fleetwright.fleet.run_reconciler            # reconcile once
    python3 -m fleetwright.fleet.run_reconciler --json
    python3 -m fleetwright.fleet.run_reconciler --grace 0  # no grace (tests)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fleetwright.fleet.fleet import (
    RUN_LOG_DIR,
    TMUX_PREFIX,
    _tmux_session_exists,
)

log = logging.getLogger(__name__)

HEADLESS_PREFIX = "headless-"
GRACE_SEC = int(os.environ.get("FLEET_RECONCILE_GRACE_SEC", "120"))


def _session_alive(run_id: str) -> bool:
    return (
        _tmux_session_exists(f"{TMUX_PREFIX}{run_id}")
        or _tmux_session_exists(f"{HEADLESS_PREFIX}{run_id}")
    )


def _age_sec(iso_ts: Optional[str]) -> Optional[float]:
    if not iso_ts:
        return None
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except Exception:
        return None


def _events_path(run_id: str) -> Path:
    return RUN_LOG_DIR / f"{run_id}.events.jsonl"


def reconcile(grace_sec: int = GRACE_SEC) -> dict:
    """Sweep non-terminal runs; close the ones whose session is dead.

    Returns a summary dict with keys: checked, alive, skipped_young,
    ingested, closed_done, closed_failed, errors.
    """
    from fleetwright.fleet import checkpoints

    summary = {
        "checked": 0, "alive": 0, "skipped_young": 0,
        "ingested": 0, "closed_done": 0, "closed_failed": 0, "errors": 0,
    }

    try:
        active = checkpoints.list_active()
    except Exception as e:
        log.warning("reconcile: list_active failed: %s", e)
        summary["errors"] += 1
        return summary

    for run in active:
        summary["checked"] += 1
        run_id = run.run_id

        if _session_alive(run_id):
            summary["alive"] += 1
            continue

        age = _age_sec(run.updated_at or run.started_at)
        if age is not None and age < grace_sec:
            summary["skipped_young"] += 1
            continue

        ev = _events_path(run_id)
        ingested_terminal = False
        if ev.exists() and ev.stat().st_size > 0:
            try:
                from fleetwright.fleet import event_ingest
                event_ingest.ingest_file(run_id, ev)
                summary["ingested"] += 1
                row = checkpoints._fetch_row(run_id)
                if row and row.get("status") in ("done", "failed", "cancelled"):
                    ingested_terminal = True
                    if row.get("status") == "failed":
                        summary["closed_failed"] += 1
                    else:
                        summary["closed_done"] += 1
            except Exception as e:
                log.warning("reconcile: ingest_file(%s) failed: %s", run_id, e)
                summary["errors"] += 1

        if not ingested_terminal:
            try:
                checkpoints.update_status(run_id, "done")
                summary["closed_done"] += 1
            except Exception as e:
                log.warning("reconcile: update_status(%s) failed: %s", run_id, e)
                summary["errors"] += 1

    return summary


def _main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="fleetwright-recon",
        description="Close lifecycle of fleet runs whose tmux session is dead.",
    )
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument(
        "--grace", type=int, default=GRACE_SEC,
        help=f"grace seconds before reaping a young run (default {GRACE_SEC})"
    )
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    summary = reconcile(grace_sec=args.grace)
    if args.json:
        print(json.dumps(summary))
    else:
        print(
            f"reconcile: checked={summary['checked']} alive={summary['alive']} "
            f"skipped_young={summary['skipped_young']} "
            f"closed_done={summary['closed_done']} closed_failed={summary['closed_failed']} "
            f"ingested={summary['ingested']} errors={summary['errors']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(_main())
