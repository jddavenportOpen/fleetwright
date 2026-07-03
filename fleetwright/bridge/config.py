"""fleetwright/bridge/config.py — bridge configuration (all env-driven, no hardcoded paths).

Import from fleetwright.config for the central config object. This module adds
bridge-specific tuning knobs and the agent command registry.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from fleetwright.config import (
    BRIDGE_HOST as HOST,
    BRIDGE_PORT as PORT,
    BRIDGE_SECRET,
    BRIDGE_LOG_DIR as LOG_DIR,
    DEV_MODE,
    FLEETWRIGHT_ROOT,
)

LOG_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG = LOG_DIR / "audit.log"

# Allowed cwd prefixes for /spawn. Request cwd must be INSIDE one of these
# after resolving symlinks. Override via BRIDGE_ALLOWED_CWD_PREFIXES (colon-separated).
def _load_cwd_prefixes() -> tuple[Path, ...]:
    env = os.environ.get("BRIDGE_ALLOWED_CWD_PREFIXES", "")
    if env:
        return tuple(Path(p).expanduser().resolve() for p in env.split(":") if p)
    # Default: only allow spawns under FLEETWRIGHT_ROOT
    return (FLEETWRIGHT_ROOT.resolve(),)


ALLOWED_CWD_PREFIXES: tuple[Path, ...] = _load_cwd_prefixes()
DEFAULT_CWD: Path = FLEETWRIGHT_ROOT.resolve()

# Claude binary discovery
_CLAUDE_CANDIDATES: tuple[Path, ...] = (
    Path("/opt/homebrew/bin/claude"),
    Path.home() / ".claude" / "local" / "claude",
    Path("/usr/local/bin/claude"),
)


def claude_binary() -> str:
    for p in _CLAUDE_CANDIDATES:
        if p.exists():
            return str(p)
    return "claude"


# Spawn permission mode for cockpit panes.
# 'bypassPermissions' is required for autonomous panes (no human at the tty).
def spawn_permission_mode() -> str:
    return (
        os.environ.get("BRIDGE_SPAWN_PERMISSION_MODE", "bypassPermissions").strip()
        or "bypassPermissions"
    )


# Session lifecycle tuning
def _session_idle_timeout_default() -> int:
    raw = os.environ.get("BRIDGE_SESSION_IDLE_TIMEOUT_SEC", "")
    if not raw:
        return 24 * 60 * 60  # 24h safety ceiling
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return 24 * 60 * 60
    return val if val >= 60 else 24 * 60 * 60


SESSION_IDLE_TIMEOUT_SEC: int = _session_idle_timeout_default()

# Grace period between tab losing focus and session being reaped (seconds)
def _session_grace_default() -> int:
    raw = os.environ.get("BRIDGE_SESSION_GRACE_AFTER_UNWARM_SEC", "")
    if not raw:
        return 180
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return 180
    return val if val >= 10 else 180


SESSION_GRACE_AFTER_UNWARM_SEC: int = _session_grace_default()

# Input-readiness gate timeout (wait for PTY to be ready before first write)
RESUME_READY_TIMEOUT_SEC: float = float(
    os.environ.get("BRIDGE_RESUME_READY_TIMEOUT_SEC", "90")
)

# Rate limiting
SPAWN_RATE_LIMIT_N: int = 10
SPAWN_RATE_LIMIT_WINDOW_SEC: int = 60 * 60  # 1 hour

# Turn watchdog
BRIDGE_TURN_MAX_DURATION_CEILING_SEC: int = int(
    os.environ.get("BRIDGE_TURN_MAX_DURATION_CEILING_SEC", str(6 * 3600))
)


def turn_max_duration_sec() -> int:
    raw = os.environ.get("BRIDGE_TURN_MAX_DURATION_SEC", "")
    if not raw:
        return 6 * 3600
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 6 * 3600


def turn_sigterm_grace_sec() -> int:
    raw = os.environ.get("BRIDGE_TURN_SIGTERM_GRACE_SEC", "")
    try:
        return max(1, int(raw)) if raw else 5
    except (TypeError, ValueError):
        return 5


def turn_heartbeat_sec() -> int:
    """SSE heartbeat interval to keep connections alive through proxies."""
    raw = os.environ.get("BRIDGE_TURN_HEARTBEAT_SEC", "")
    try:
        val = int(raw) if raw else 10
        return max(0, val)
    except (TypeError, ValueError):
        return 10


# ── Agent command registry ─────────────────────────────────────────────────
# Maps agent names to Python module paths. This is the config-driven replacement
# for the hardcoded fallback dict in the original bridge.
# Users extend this by setting BRIDGE_AGENT_COMMANDS_FILE to a JSON file:
#   {"commands": {"my_agent": "my_package.agents.my_agent"}}

_DEFAULT_COMMANDS_FILE = Path(__file__).parent / "agent_commands.json"
_ENV_COMMANDS_FILE = os.environ.get("BRIDGE_AGENT_COMMANDS_FILE", "")

_FALLBACK_COMMANDS: dict[str, str] = {
    # Example agents (users replace these with their own)
    "work":     "fleetwright.agents.examples.work",
    "personal": "fleetwright.agents.examples.personal",
}


def _load_agent_commands() -> dict[str, Callable[[str, list[str]], list[str]]]:
    from fleetwright.sdk import model_registry as _mr
    try:
        model = _mr.cli_id("agent")
    except Exception:
        model = "claude-sonnet-4-6"

    def _agent_argv(module: str) -> Callable[[str, list[str]], list[str]]:
        python = os.environ.get("FLEETWRIGHT_PYTHON", "python3")

        def build(prompt: str, files: list[str]) -> list[str]:
            argv: list[str] = [python, "-m", module, prompt]
            for f in files:
                argv.extend(["--file", f])
            return argv

        return build

    modules = dict(_FALLBACK_COMMANDS)

    # Load from env-specified file
    if _ENV_COMMANDS_FILE:
        try:
            data = json.loads(Path(_ENV_COMMANDS_FILE).read_text())
            if isinstance(data.get("commands"), dict):
                modules.update(data["commands"])
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("failed to load agent commands: %s", e)

    # Load from default commands file
    elif _DEFAULT_COMMANDS_FILE.exists():
        try:
            data = json.loads(_DEFAULT_COMMANDS_FILE.read_text())
            if isinstance(data.get("commands"), dict):
                modules.update(data["commands"])
        except Exception:
            pass

    return {name: _agent_argv(module) for name, module in modules.items()}


AGENT_COMMANDS: dict[str, Callable[[str, list[str]], list[str]]] = _load_agent_commands()
AGENT_CWD: Path = FLEETWRIGHT_ROOT.resolve()
