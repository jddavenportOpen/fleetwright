"""fleetwright/bridge/pty_manager.py — PTY session manager stub.

The full PTY manager (persistent supervisor, crash recovery, SSE streaming)
will be extracted in M4 (cockpit extraction). This stub satisfies
the lazy imports in bridge/routes/sessions.py and bridge/routes/domains.py.

To install a real pty_manager, replace this file with an implementation that
provides the same public API and set PTY_MANAGER_ENABLED=1.
"""
from __future__ import annotations

import os

_ENABLED = os.environ.get("PTY_MANAGER_ENABLED", "0").strip() not in ("", "0", "false", "no")


class PTYNotAvailableError(NotImplementedError):
    """Raised when PTY manager is called but not yet installed."""


def list_sessions() -> list[dict]:
    """Return all active PTY sessions."""
    if _ENABLED:
        raise PTYNotAvailableError(
            "PTY_MANAGER_ENABLED=1 but no real pty_manager is installed. "
            "See cockpit/README.md for M4 extraction notes."
        )
    return []


async def spawn_session(
    *,
    name=None,
    cwd=None,
    domain=None,
    model=None,
    permission_mode=None,
    add_dirs=None,
    env=None,
) -> str:
    """Spawn a new PTY session. Raises PTYNotAvailableError until M4."""
    raise PTYNotAvailableError(
        "pty_manager not available in M2 — PTY session management is extracted in M4. "
        "Use the fleet API (/api/fleet) to spawn headless Claude Code workers."
    )


async def kill_session(sid: str) -> None:
    """Kill a PTY session by SID."""
    raise PTYNotAvailableError("pty_manager not available in M2 — see cockpit/README.md")


async def resume_session(sid: str) -> str:
    """Resume a dead PTY session."""
    raise PTYNotAvailableError("pty_manager not available in M2 — see cockpit/README.md")
