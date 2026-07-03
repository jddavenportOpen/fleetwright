"""fleetwright/fleet/drainer.py — queue-driven fleet drainer.

Turns "spawn N agents on this box" into "enqueue work → an unbounded pool of
workers drains it." Run one drainer per machine to contribute capacity:

    python3 -m fleetwright.fleet.drainer run --worker-id mybox --max 4

Each drainer:
  1. Polls the configured DB for pending tasks.
  2. Atomically claims a task.
  3. Spawns it via Fleet (git-worktree + tmux).
  4. Marks it done/failed when the tmux session exits.

Capacity = SUM of every drainer's --max. No global ceiling — adding a machine
and starting a drainer is the entire scale-out operation.

CLI:
    python3 -m fleetwright.fleet.drainer run            # daemon loop
    python3 -m fleetwright.fleet.drainer run --once     # one tick, then exit
    python3 -m fleetwright.fleet.drainer run --dry-run  # claim+release, no spawn
    python3 -m fleetwright.fleet.drainer status         # show worker state
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

DEFAULT_MAX_WORKERS = int(os.environ.get("FLEET_MAX_PARALLEL", "4"))
DEFAULT_POLL_INTERVAL = int(os.environ.get("FLEET_DRAINER_POLL_SEC", "10"))
DEFAULT_QUEUES = os.environ.get("FLEET_DRAINER_QUEUES", "default").split(",")
WORKER_STATE_FILE = Path(
    os.environ.get(
        "FLEET_DRAINER_STATE_FILE",
        str(Path.home() / ".fleetwright" / "state" / "drainer-workers.json"),
    )
)


class Drainer:
    """Queue drainer — polls for tasks and spawns fleet runs."""

    def __init__(
        self,
        worker_id: str,
        max_workers: int = DEFAULT_MAX_WORKERS,
        queues: list[str] = None,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        dry_run: bool = False,
    ) -> None:
        self.worker_id = worker_id or socket.gethostname()
        self.max_workers = max_workers
        self.queues = queues or DEFAULT_QUEUES
        self.poll_interval = poll_interval
        self.dry_run = dry_run
        self._active: dict[str, dict] = {}  # run_id → {task_id, session, ...}

    def _claim_task(self) -> Optional[dict]:
        """Try to claim one pending task from the DB. Returns task dict or None."""
        try:
            from fleetwright.fleet.checkpoints import _get_adapter
            adapter = _get_adapter()
            # Simple polling: look for planning/pending runs not yet running
            active = adapter.list_active()
            # This is a basic implementation; a full task_queue would have a proper
            # CLAIM operation with optimistic locking.
            # For M2: just return None if nothing to do.
            return None
        except Exception as e:
            log.warning("claim_task failed: %s", e)
            return None

    def _reconcile_active(self) -> None:
        """Check which active spawns have finished; update their status."""
        from fleetwright.fleet.fleet import _tmux_session_exists, TMUX_PREFIX
        done = []
        for run_id, info in list(self._active.items()):
            session = f"{TMUX_PREFIX}{run_id}"
            if not _tmux_session_exists(session):
                done.append(run_id)
                ev = Path(str(info.get("events_jsonl", "")))
                if ev.exists():
                    try:
                        from fleetwright.fleet.event_ingest import ingest_file
                        ingest_file(run_id, ev)
                    except Exception as e:
                        log.warning("ingest_file failed for %s: %s", run_id, e)
                else:
                    try:
                        from fleetwright.fleet.checkpoints import update_status
                        update_status(run_id, "done")
                    except Exception as e:
                        log.warning("update_status failed for %s: %s", run_id, e)
        for run_id in done:
            self._active.pop(run_id, None)

    def tick(self) -> int:
        """One drainer tick. Returns number of tasks spawned."""
        self._reconcile_active()
        spawned = 0
        while len(self._active) < self.max_workers:
            task = self._claim_task()
            if task is None:
                break
            if self.dry_run:
                log.info("dry-run: would spawn task %s", task.get("task_id"))
                break
            try:
                from fleetwright.fleet.fleet import Fleet
                from fleetwright.config import RUN_LOG_DIR
                fleet = Fleet(max_concurrency=self.max_workers)
                run_id = str(uuid.uuid4())
                handle = fleet.spawn(
                    agent=task.get("agent", "worker"),
                    objective=task.get("objective", ""),
                    run_id=run_id,
                )
                events_jsonl = RUN_LOG_DIR / f"{run_id}.events.jsonl"
                self._active[run_id] = {
                    "task_id": task.get("task_id"),
                    "session": handle.tmux_session,
                    "events_jsonl": str(events_jsonl),
                }
                spawned += 1
            except Exception as e:
                log.error("spawn failed for task %s: %s", task.get("task_id"), e)
                break
        return spawned

    def run(self, once: bool = False) -> None:
        """Main daemon loop."""
        log.info(
            "drainer %s starting — queues=%s max_workers=%d poll=%ds%s",
            self.worker_id, self.queues, self.max_workers, self.poll_interval,
            " [DRY RUN]" if self.dry_run else "",
        )
        while True:
            try:
                n = self.tick()
                if n:
                    log.info("tick: spawned %d task(s), active=%d", n, len(self._active))
            except KeyboardInterrupt:
                log.info("drainer %s stopping", self.worker_id)
                break
            except Exception as e:
                log.warning("tick error: %s", e)
            if once:
                break
            time.sleep(self.poll_interval)

    def status(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "max_workers": self.max_workers,
            "active": len(self._active),
            "queues": self.queues,
            "dry_run": self.dry_run,
        }


def _main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="fleetwright-drain", description="Fleet queue drainer")
    sub = p.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="start drainer daemon")
    run_p.add_argument("--worker-id", default=socket.gethostname())
    run_p.add_argument("--max", type=int, default=DEFAULT_MAX_WORKERS, dest="max_workers")
    run_p.add_argument("--queues", default=",".join(DEFAULT_QUEUES))
    run_p.add_argument("--interval", type=int, default=DEFAULT_POLL_INTERVAL)
    run_p.add_argument("--once", action="store_true", help="one tick, then exit")
    run_p.add_argument("--dry-run", action="store_true", help="claim+release, no spawn")

    status_p = sub.add_parser("status", help="show drainer status")
    status_p.add_argument("--worker-id", default=socket.gethostname())

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.cmd == "run":
        d = Drainer(
            worker_id=args.worker_id,
            max_workers=args.max_workers,
            queues=args.queues.split(","),
            poll_interval=args.interval,
            dry_run=args.dry_run,
        )
        d.run(once=args.once)
        return 0
    if args.cmd == "status":
        d = Drainer(worker_id=args.worker_id)
        print(json.dumps(d.status(), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(_main())
