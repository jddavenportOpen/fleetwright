"""fleetwright/bridge/pty_manager.py — Bridge session manager (M4).

Each session wraps Claude Code's --output-format stream-json transport.
Sessions are persistent in memory (process lifetime); each turn spawns a
subprocess with --resume <session_id> to continue the conversation.

Public API:
  list_sessions()                      → list[dict]
  spawn_session(*, name, cwd, ...)     → str  (sid)
  kill_session(sid)                    → None
  resume_session(sid)                  → str  (new sid)
  send_turn(sid, message, max_dur)     → AsyncIterator[str]  (SSE chunks)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Optional

log = logging.getLogger("bridge.pty_manager")

# ── Session state ─────────────────────────────────────────────────────────────
@dataclass
class Session:
    sid: str
    name: str
    cwd: str
    domain: Optional[str]
    model: str
    cc_session_id: Optional[str] = None   # claude --resume target; set after first turn
    status: str = "idle"                   # idle | busy | dead
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "sid": self.sid,
            "name": self.name,
            "cwd": self.cwd,
            "domain": self.domain,
            "model": self.model,
            "cc_session_id": self.cc_session_id,
            "status": self.status,
            "started_at": self.started_at,
        }

_sessions: dict[str, Session] = {}

# ── Claude binary ─────────────────────────────────────────────────────────────
def _claude_binary() -> str:
    from fleetwright.bridge.config import claude_binary
    return claude_binary()

# ── Public API ────────────────────────────────────────────────────────────────
def list_sessions() -> list[dict]:
    return [s.to_dict() for s in _sessions.values() if s.status != "dead"]

async def spawn_session(
    *,
    name: Optional[str] = None,
    cwd: Optional[str] = None,
    domain: Optional[str] = None,
    model: Optional[str] = None,
    permission_mode: Optional[str] = None,
    add_dirs: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> str:
    from fleetwright.config import FLEETWRIGHT_ROOT
    sid = str(uuid.uuid4())
    resolved_cwd = str(Path(cwd or str(FLEETWRIGHT_ROOT)).expanduser().resolve())
    resolved_model = model or _default_model()
    resolved_name = name or f"session-{sid[:8]}"

    s = Session(
        sid=sid,
        name=resolved_name,
        cwd=resolved_cwd,
        domain=domain,
        model=resolved_model,
    )
    _sessions[sid] = s
    log.info("spawned session %s (name=%s, domain=%s, cwd=%s)", sid, resolved_name, domain, resolved_cwd)
    return sid

async def kill_session(sid: str) -> None:
    if sid not in _sessions:
        raise KeyError(f"session {sid!r} not found")
    _sessions[sid].status = "dead"
    log.info("killed session %s", sid)

async def resume_session(sid: str) -> str:
    if sid not in _sessions:
        raise KeyError(f"session {sid!r} not found")
    old = _sessions[sid]
    new_sid = str(uuid.uuid4())
    new_session = Session(
        sid=new_sid,
        name=old.name,
        cwd=old.cwd,
        domain=old.domain,
        model=old.model,
        cc_session_id=old.cc_session_id,   # preserve resume target
        status="idle",
    )
    _sessions[old.sid].status = "dead"
    _sessions[new_sid] = new_session
    log.info("resumed session %s → %s", sid, new_sid)
    return new_sid

async def send_turn(
    sid: str,
    message: str,
    max_duration_sec: int = 21600,
) -> AsyncIterator[str]:
    if sid not in _sessions:
        raise KeyError(f"session {sid!r} not found")
    session = _sessions[sid]
    if session.status == "dead":
        raise RuntimeError(f"session {sid} is dead; call resume_session first")
    if session.status == "busy":
        raise RuntimeError(f"session {sid} is busy; wait for the current turn to complete")

    session.status = "busy"
    try:
        async for chunk in _stream_turn(session, message, max_duration_sec):
            yield chunk
    finally:
        session.status = "idle"

# ── Internal ──────────────────────────────────────────────────────────────────
def _default_model() -> str:
    try:
        from fleetwright.sdk import model_registry as mr
        return mr.cli_id("agent")
    except Exception:
        return "claude-sonnet-4-6"

async def _stream_turn(
    session: Session,
    message: str,
    max_duration_sec: int,
) -> AsyncIterator[str]:
    claude = _claude_binary()
    argv = [claude]
    if session.cc_session_id:
        argv += ["--resume", session.cc_session_id]
    argv += [
        "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--model", session.model,
        "--dangerously-skip-permissions",
        message,
    ]

    env = dict(os.environ)
    # Strip metered API keys so the worker uses the Max subscription
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)

    log.debug("spawning claude: %s", argv)
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=session.cwd,
        env=env,
    )

    session_id_captured = False

    try:
        from fleetwright.bridge.config import turn_heartbeat_sec
        heartbeat_interval = turn_heartbeat_sec()
    except Exception:
        heartbeat_interval = 10

    last_heartbeat = asyncio.get_event_loop().time()

    async def _read_stdout() -> AsyncIterator[str]:
        nonlocal session_id_captured, last_heartbeat
        assert proc.stdout is not None
        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if not line:
                continue
            now = asyncio.get_event_loop().time()
            if heartbeat_interval > 0 and now - last_heartbeat >= heartbeat_interval:
                yield ": heartbeat\n\n"
                last_heartbeat = now
            try:
                event = json.loads(line)
                # Capture session_id from init event
                if (
                    not session_id_captured
                    and event.get("type") == "system"
                    and event.get("subtype") == "init"
                    and event.get("session_id")
                ):
                    session.cc_session_id = event["session_id"]
                    session_id_captured = True
                    log.info("captured cc_session_id=%s for sid=%s", session.cc_session_id, session.sid)
                yield f"data: {json.dumps(event)}\n\n"
            except json.JSONDecodeError:
                # Pass raw line as a text event
                yield f"data: {json.dumps({'type': 'output', 'text': line})}\n\n"

    try:
        async with asyncio.timeout(max_duration_sec):
            async for chunk in _read_stdout():
                yield chunk
    except TimeoutError:
        proc.kill()
        yield f"data: {json.dumps({'type': 'error', 'error': 'turn timed out'})}\n\n"
        return

    await proc.wait()
    if proc.returncode != 0:
        stderr_data = b""
        if proc.stderr:
            try:
                stderr_data = await asyncio.wait_for(proc.stderr.read(), timeout=2.0)
            except Exception:
                pass
        err_msg = stderr_data.decode("utf-8", errors="replace").strip()[-500:] if stderr_data else f"exit code {proc.returncode}"
        yield f"data: {json.dumps({'type': 'error', 'error': err_msg})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
