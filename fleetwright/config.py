"""Central config module — all env-driven settings in one place.

Every Fleetwright subpackage reads from here rather than directly from os.environ,
so the full config surface is discoverable in one file.
"""
from __future__ import annotations

import os
from pathlib import Path

# ── Root ──────────────────────────────────────────────────────────────────────
HOME = Path.home()

# FLEETWRIGHT_ROOT is the user-writable runtime directory.
# Default: ~/.fleetwright
FLEETWRIGHT_ROOT = Path(
    os.environ.get("FLEETWRIGHT_ROOT", str(HOME / ".fleetwright"))
).expanduser()

# ── Fleet engine ──────────────────────────────────────────────────────────────
WORKTREE_ROOT = Path(
    os.environ.get("FLEET_WORKTREE_ROOT", str(FLEETWRIGHT_ROOT / ".fleet-worktrees"))
).expanduser()

RUN_LOG_DIR = Path(
    os.environ.get("FLEET_RUN_LOG_DIR", str(FLEETWRIGHT_ROOT / "logs" / "runs"))
).expanduser()

# Default git base branch for worktree spawning.
FLEET_BASE_BRANCH = os.environ.get("FLEET_BASE_BRANCH", "main")

# Git repository root to use for worktree operations.
# In a self-hosted install this is the user's project repo.
# Override with FLEET_GIT_ROOT if your project lives elsewhere.
FLEET_GIT_ROOT = Path(
    os.environ.get("FLEET_GIT_ROOT", str(HOME))
).expanduser()

# ── Database ──────────────────────────────────────────────────────────────────
DB_BACKEND = os.environ.get("DB_BACKEND", "sqlite").lower()
SQLITE_PATH = Path(
    os.environ.get("SQLITE_PATH", str(FLEETWRIGHT_ROOT / "state" / "fleetwright.db"))
).expanduser()
DATABASE_URL = os.environ.get("DATABASE_URL", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or ""
)

# ── Bridge ────────────────────────────────────────────────────────────────────
BRIDGE_HOST = os.environ.get("HOST", "127.0.0.1")
BRIDGE_PORT = int(os.environ.get("PORT", "8787"))
BRIDGE_SECRET = os.environ.get("BRIDGE_SECRET", "")
DEV_MODE = os.environ.get("DEV_MODE", "").lower() in {"1", "true", "yes"}

BRIDGE_LOG_DIR = Path(
    os.environ.get("LOG_DIR", str(FLEETWRIGHT_ROOT / "logs" / "bridge"))
).expanduser()

# ── Domain registry ───────────────────────────────────────────────────────────
_DOMAINS_FILE_ENV = os.environ.get("FLEETWRIGHT_DOMAINS_FILE", "")
if _DOMAINS_FILE_ENV:
    DOMAINS_FILE = Path(_DOMAINS_FILE_ENV).expanduser()
else:
    # Look next to the running package root
    DOMAINS_FILE = Path(__file__).resolve().parent.parent / "config" / "domains.yaml"

# ── Notifications ─────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ── State dir (circuit breakers, domain registry, etc.) ──────────────────────
STATE_DIR = Path(
    os.environ.get("FLEETWRIGHT_STATE_DIR", str(FLEETWRIGHT_ROOT / "state"))
).expanduser()
