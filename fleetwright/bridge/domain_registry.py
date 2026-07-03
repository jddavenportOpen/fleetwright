"""fleetwright/bridge/domain_registry.py — YAML-driven persistent domain-agent registry.

Maps domain names to their singleton bridge sessions. Unlike the original which
had hardcoded domain names (health, family, etc.), this is fully config-driven:
domains come from config/domains.yaml (or FLEETWRIGHT_DOMAINS_FILE).

Storage: <STATE_DIR>/domain-agents.json — one row per domain.

    {
      "work": {
        "domain": "work",
        "sid": "<current bridge sid>",
        "cc_session_id": "<claude --resume target>",
        "cwd": "/home/user/fleetwright-domains/work",
        "started_at": "...",
        "updated_at": "..."
      },
      ...
    }

Design:
  - NEVER raises. The bridge must not crash because the registry is unavailable.
  - One file, atomic write, threading.Lock.
  - cc_session_id is the resume target (stable across restarts); sid is the
    current bridge session ID (changes on each resume).
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_log = logging.getLogger("bridge.domain_registry")

_lock = threading.RLock()
_cache: dict[str, dict[str, Any]] | None = None


def _state_file() -> Path:
    from fleetwright.config import STATE_DIR
    return Path(
        __import__("os").environ.get("DOMAIN_REGISTRY_FILE", str(STATE_DIR / "domain-agents.json"))
    ).expanduser()


# ── Domain config (from YAML) ─────────────────────────────────────────────
def load_domain_configs() -> list[dict[str, Any]]:
    """Load domain definitions from config/domains.yaml."""
    from fleetwright.config import DOMAINS_FILE
    if not DOMAINS_FILE.exists():
        _log.debug("domains file not found at %s", DOMAINS_FILE)
        return []
    try:
        import yaml
        with open(DOMAINS_FILE, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data.get("domains") or []
    except Exception as e:
        _log.warning("failed to load domains config: %s", e)
        return []


def get_domain_names() -> list[str]:
    """Return all configured domain names."""
    try:
        return [d["name"] for d in load_domain_configs() if d.get("name")]
    except Exception:
        return []


def get_domain_config(name: str) -> Optional[dict[str, Any]]:
    """Return the config dict for a specific domain, or None."""
    for d in load_domain_configs():
        if d.get("name") == name:
            return d
    return None


# ── Registry read/write ───────────────────────────────────────────────────
def _load_file() -> dict[str, dict[str, Any]]:
    global _cache
    if _cache is not None:
        return _cache
    sf = _state_file()
    try:
        if sf.exists():
            _cache = json.loads(sf.read_text(encoding="utf-8"))
            return _cache
    except Exception as e:
        _log.warning("domain registry load failed: %s", e)
    _cache = {}
    return _cache


def _save_file(data: dict[str, dict[str, Any]]) -> None:
    global _cache
    _cache = data
    sf = _state_file()
    try:
        sf.parent.mkdir(parents=True, exist_ok=True)
        import tempfile, os
        fd, tmp = tempfile.mkstemp(dir=sf.parent, prefix=".domain-agents-")
        with __import__("os").fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, sf)
    except Exception as e:
        _log.warning("domain registry save failed: %s", e)


# ── Public API ────────────────────────────────────────────────────────────
def register(
    domain: str,
    sid: str,
    cc_session_id: str,
    cwd: str,
) -> None:
    """Record that domain's brain is now running as bridge session sid."""
    with _lock:
        data = _load_file()
        now = datetime.now(timezone.utc).isoformat()
        data[domain] = {
            "domain": domain,
            "sid": sid,
            "cc_session_id": cc_session_id,
            "cwd": cwd,
            "started_at": data.get(domain, {}).get("started_at", now),
            "updated_at": now,
        }
        _save_file(data)
    _log.info("registered domain %s → sid %s", domain, sid)


def get(domain: str) -> Optional[dict[str, Any]]:
    """Return the current registration for domain, or None if not registered."""
    with _lock:
        return _load_file().get(domain)


def update_sid(domain: str, new_sid: str) -> None:
    """Update sid after a resume (cc_session_id stays stable)."""
    with _lock:
        data = _load_file()
        if domain not in data:
            return
        data[domain]["sid"] = new_sid
        data[domain]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_file(data)


def clear(domain: str) -> None:
    """Remove a domain registration (e.g. when the session is explicitly stopped)."""
    with _lock:
        data = _load_file()
        data.pop(domain, None)
        _save_file(data)
    _log.info("cleared domain %s from registry", domain)


def list_all() -> dict[str, dict[str, Any]]:
    """Return all current registrations."""
    with _lock:
        return dict(_load_file())


def invalidate_cache() -> None:
    """Force a file re-read on next access."""
    global _cache
    with _lock:
        _cache = None
