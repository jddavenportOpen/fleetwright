#!/usr/bin/env python3
"""
fleet.py — Worktree+tmux supervisor for parallel Claude Code instances.

The runtime that makes "N Claude Codes running in parallel" actually work.
Each agent gets its own git worktree (isolated filesystem snapshot) inside
its own tmux session (detached, supervisable, output streamable).

Per-spawn lifecycle:
  1. Mint a run_id (UUID4).
  2. Create a git worktree on branch `task/<run_id>` under WORKTREE_ROOT.
  3. Write a `WORKPLAN.md` so the agent re-reads its plan each loop.
  4. Spawn `tmux new -d -s fleet-<run_id>` running headless
     `claude --session-id <run_id> -p --output-format stream-json --verbose
     "<objective>"`, with stdout → <run_id>.events.jsonl and stderr →
     <run_id>.events.err. ANTHROPIC_API_KEY/AUTH_TOKEN are scrubbed so the
     worker uses the Max subscription rather than the metered API.
  5. Return a RunHandle. The caller is responsible for tracking it.

Run lifecycle is CLOSED by fleetwright.fleet.run_reconciler (cron every few
minutes): when the tmux session exits, the reconciler reads the events file,
attributes cost, and moves the agent_runs row to done/failed.

Safety constraints (NON-NEGOTIABLE):
  - Worktrees go in WORKTREE_ROOT ONLY.
  - Tmux session names start with `fleet-` ONLY.
  - cancel() verifies session prefix before SIGTERM.
  - reap() verifies worktree path prefix before deletion.

CLI:
    python3 -m fleetwright.fleet.fleet spawn <agent> <objective>
    python3 -m fleetwright.fleet.fleet list
    python3 -m fleetwright.fleet.fleet cancel <run_id>
    python3 -m fleetwright.fleet.fleet reap
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from fleetwright.sdk import model_registry as _mr

logger = logging.getLogger(__name__)

# ── Layout ─────────────────────────────────────────────────────────────────
from fleetwright.config import WORKTREE_ROOT, RUN_LOG_DIR, FLEET_BASE_BRANCH, FLEET_GIT_ROOT

TMUX_PREFIX = "fleet-"
REAP_AGE_SEC = 24 * 60 * 60  # 24h — only GC worktrees older than this

# Ensure runtime dirs exist at import time.
WORKTREE_ROOT.mkdir(parents=True, exist_ok=True)
RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Optional checkpoint dependency ────────────────────────────────────────
try:
    from fleetwright.fleet.checkpoints import (
        create_run as _create_run,
        update_status as _update_status,
    )
    _HAVE_CHECKPOINTS = True
except Exception:
    _HAVE_CHECKPOINTS = False

    def _create_run(*_a, **_kw) -> str:
        return str(uuid.uuid4())

    def _update_status(*_a, **_kw) -> None:
        return None


# ── Errors ─────────────────────────────────────────────────────────────────
class FleetError(Exception):
    """Base error for fleet operations."""


class FleetCapacityError(FleetError):
    """Raised when spawn() is called while at max_concurrency."""


class FleetSafetyError(FleetError):
    """Raised when a path/session would violate the safety prefix rules."""


# ── Data ───────────────────────────────────────────────────────────────────
@dataclass
class RunHandle:
    """Lightweight handle for one fleet run."""

    run_id: str
    agent: str
    objective: str
    worktree_path: str
    tmux_session: str
    pid: Optional[int] = None
    status: str = "pending"
    parent_run_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Subprocess helper (mockable) ───────────────────────────────────────────
def _run(
    argv: list[str], *, check: bool = True, cwd: Optional[str] = None
) -> subprocess.CompletedProcess:
    return subprocess.run(argv, check=check, capture_output=True, text=True, cwd=cwd)


# ── Safety guards ──────────────────────────────────────────────────────────
def _assert_safe_worktree(path: Path) -> None:
    resolved = path.resolve()
    root = WORKTREE_ROOT.resolve()
    if not str(resolved).startswith(str(root) + os.sep) and resolved != root:
        raise FleetSafetyError(f"refusing to touch {resolved} — not under {root}")


def _assert_safe_session(name: str) -> None:
    if not name.startswith(TMUX_PREFIX):
        raise FleetSafetyError(
            f"refusing to act on tmux session {name!r} — must start with {TMUX_PREFIX!r}"
        )


# ── tmux helpers ───────────────────────────────────────────────────────────
def _tmux_session_exists(name: str) -> bool:
    cp = _run(["tmux", "has-session", "-t", name], check=False)
    return cp.returncode == 0


def _tmux_list_fleet_sessions() -> list[str]:
    cp = _run(["tmux", "list-sessions", "-F", "#{session_name}"], check=False)
    if cp.returncode != 0:
        return []
    return [
        line.strip()
        for line in cp.stdout.splitlines()
        if line.strip().startswith(TMUX_PREFIX)
    ]


def _tmux_session_pid(name: str) -> Optional[int]:
    cp = _run(
        ["tmux", "list-panes", "-t", name, "-F", "#{pane_pid}"],
        check=False,
    )
    if cp.returncode != 0 or not cp.stdout.strip():
        return None
    try:
        return int(cp.stdout.splitlines()[0].strip())
    except (ValueError, IndexError):
        return None


# ── Fleet ──────────────────────────────────────────────────────────────────
class Fleet:
    """Supervisor for parallel Claude Code worktrees."""

    DEFAULT_MAX_CONCURRENCY = 10

    def __init__(self, max_concurrency: int | None = None) -> None:
        if max_concurrency is None:
            env_val = os.environ.get("FLEET_MAX_PARALLEL", "").strip()
            if env_val:
                try:
                    max_concurrency = int(env_val)
                except ValueError:
                    max_concurrency = self.DEFAULT_MAX_CONCURRENCY
            else:
                max_concurrency = self.DEFAULT_MAX_CONCURRENCY
        if max_concurrency < 1:
            raise ValueError(f"max_concurrency must be >=1 (got {max_concurrency})")
        self.max_concurrency = max_concurrency
        WORKTREE_ROOT.mkdir(parents=True, exist_ok=True)
        RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)

    def spawn(
        self,
        agent: str,
        objective: str,
        parent_run_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> RunHandle:
        active = self.list_active()
        if len(active) >= self.max_concurrency:
            raise FleetCapacityError(
                f"fleet at capacity ({len(active)}/{self.max_concurrency}); "
                "caller should retry or queue"
            )

        caller_supplied_run_id = run_id is not None
        run_id = run_id or str(uuid.uuid4())
        if not caller_supplied_run_id:
            try:
                _create_run(
                    run_id=run_id,
                    agent=agent,
                    objective=objective,
                    parent_run_id=parent_run_id,
                )
            except Exception as e:
                logger.warning("checkpoints.create_run failed: %s", e)

        worktree = WORKTREE_ROOT / run_id
        _assert_safe_worktree(worktree)
        branch = f"task/{run_id}"
        session = f"{TMUX_PREFIX}{run_id}"

        # 1. git worktree
        try:
            _run(
                ["git", "worktree", "add", "-b", branch, str(worktree), FLEET_BASE_BRANCH],
                cwd=str(FLEET_GIT_ROOT),
            )
        except subprocess.CalledProcessError as e:
            raise FleetError(
                f"git worktree add failed: {e.stderr or e.stdout or e}"
            ) from e

        # 2. WORKPLAN.md (re-read each loop — Manus pattern)
        worktree.mkdir(parents=True, exist_ok=True)
        plan = worktree / "WORKPLAN.md"
        plan.write_text(
            f"# WORKPLAN — run {run_id}\n\n"
            f"**Agent:** {agent}\n"
            f"**Spawned:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**Parent run:** {parent_run_id or '(none)'}\n\n"
            f"## Objective\n\n{objective}\n\n"
            f"## Notes\n\n"
            f"- Re-read this file at the start of each loop iteration.\n"
            f"- Update it with progress / blockers as you work.\n"
            f"- On completion, leave this worktree intact for human review.\n",
            encoding="utf-8",
        )

        # 3. tmux session running HEADLESS claude with stream-json transport.
        events_jsonl = RUN_LOG_DIR / f"{run_id}.events.jsonl"
        events_err = RUN_LOG_DIR / f"{run_id}.events.err"

        try:
            agent_model = _mr.cli_id("agent")
        except Exception:
            agent_model = "claude-sonnet-4-6"

        claude_argv = [
            "claude", "--session-id", run_id, "-p",
            "--output-format", "stream-json", "--verbose",
            "--model", agent_model,
            "--effort", "max",
            objective,
        ]
        inner = (
            f"cd {shlex.quote(str(worktree))} && "
            f"env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN "
            f"{' '.join(shlex.quote(a) for a in claude_argv)} "
            f"> {shlex.quote(str(events_jsonl))} 2> {shlex.quote(str(events_err))}"
        )
        try:
            _run(["tmux", "new-session", "-d", "-s", session, inner])
        except subprocess.CalledProcessError as e:
            self._destroy_worktree(worktree, branch)
            raise FleetError(
                f"tmux new-session failed: {e.stderr or e.stdout or e}"
            ) from e

        pid = _tmux_session_pid(session)
        try:
            _update_status(run_id=run_id, status="running")
        except Exception:
            pass

        return RunHandle(
            run_id=run_id,
            agent=agent,
            objective=objective,
            worktree_path=str(worktree),
            tmux_session=session,
            pid=pid,
            status="running",
            parent_run_id=parent_run_id,
        )

    def list_active(self) -> list[RunHandle]:
        """Enumerate worktrees and reconcile against live tmux sessions."""
        out: list[RunHandle] = []
        if not WORKTREE_ROOT.exists():
            return out
        sessions = set(_tmux_list_fleet_sessions())
        for child in sorted(WORKTREE_ROOT.iterdir()):
            if not child.is_dir():
                continue
            run_id = child.name
            session = f"{TMUX_PREFIX}{run_id}"
            alive = session in sessions
            if not alive:
                continue
            pid = _tmux_session_pid(session)
            objective = ""
            agent = "unknown"
            plan = child / "WORKPLAN.md"
            if plan.exists():
                try:
                    text = plan.read_text(encoding="utf-8", errors="replace")
                    for line in text.splitlines():
                        if line.startswith("**Agent:**"):
                            agent = line.split("**Agent:**", 1)[1].strip()
                        if line.startswith("## Objective"):
                            idx = text.splitlines().index(line)
                            for nxt in text.splitlines()[idx + 1:]:
                                if nxt.strip():
                                    objective = nxt.strip()
                                    break
                            break
                except Exception:
                    pass
            out.append(
                RunHandle(
                    run_id=run_id,
                    agent=agent,
                    objective=objective,
                    worktree_path=str(child),
                    tmux_session=session,
                    pid=pid,
                    status="running",
                )
            )
        return out

    def cancel(self, run_id: str) -> bool:
        """SIGTERM the tmux session for run_id. Returns True on success."""
        session = f"{TMUX_PREFIX}{run_id}"
        _assert_safe_session(session)
        if not _tmux_session_exists(session):
            return False
        deadline = time.time() + 2.0
        try:
            _run(["tmux", "kill-session", "-t", session], check=False)
        except Exception as e:
            logger.warning("tmux kill-session failed for %s: %s", session, e)
            return False
        while time.time() < deadline:
            if not _tmux_session_exists(session):
                try:
                    _update_status(run_id=run_id, status="cancelled")
                except Exception:
                    pass
                return True
            time.sleep(0.1)
        return False

    def reap(self) -> int:
        """GC worktrees where tmux is dead AND mtime > REAP_AGE_SEC."""
        if not WORKTREE_ROOT.exists():
            return 0
        live_sessions = set(_tmux_list_fleet_sessions())
        now = time.time()
        reaped = 0
        for child in sorted(WORKTREE_ROOT.iterdir()):
            if not child.is_dir():
                continue
            run_id = child.name
            session = f"{TMUX_PREFIX}{run_id}"
            if session in live_sessions:
                continue
            try:
                age = now - child.stat().st_mtime
            except OSError:
                continue
            if age < REAP_AGE_SEC:
                continue
            try:
                self._destroy_worktree(child, f"task/{run_id}")
                reaped += 1
            except Exception as e:
                logger.warning("reap failed for %s: %s", child, e)
        return reaped

    def _destroy_worktree(self, path: Path, branch: str) -> None:
        _assert_safe_worktree(path)
        try:
            _run(
                ["git", "worktree", "remove", "--force", str(path)],
                cwd=str(FLEET_GIT_ROOT),
                check=False,
            )
        except Exception as e:
            logger.warning("git worktree remove failed for %s: %s", path, e)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        _run(
            ["git", "branch", "-D", branch],
            cwd=str(FLEET_GIT_ROOT),
            check=False,
        )


# ── CLI ────────────────────────────────────────────────────────────────────
def _main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="fleet", description="Fleetwright fleet engine CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_spawn = sub.add_parser("spawn", help="spawn a new fleet run")
    sp_spawn.add_argument("agent")
    sp_spawn.add_argument("objective")
    sp_spawn.add_argument("--parent", default=None)

    sub.add_parser("list", help="list active fleet runs")

    sp_cancel = sub.add_parser("cancel", help="cancel a fleet run")
    sp_cancel.add_argument("run_id")

    sub.add_parser("reap", help="GC dead worktrees older than 24h")

    args = p.parse_args(argv)
    fleet = Fleet()
    if args.cmd == "spawn":
        h = fleet.spawn(args.agent, args.objective, parent_run_id=args.parent)
        print(json.dumps(h.to_dict(), indent=2))
        return 0
    if args.cmd == "list":
        rows = fleet.list_active()
        print(json.dumps([r.to_dict() for r in rows], indent=2))
        return 0
    if args.cmd == "cancel":
        ok = fleet.cancel(args.run_id)
        print(json.dumps({"cancelled": ok, "run_id": args.run_id}))
        return 0 if ok else 1
    if args.cmd == "reap":
        n = fleet.reap()
        print(json.dumps({"reaped": n}))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(_main())
