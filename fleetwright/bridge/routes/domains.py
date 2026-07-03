"""fleetwright/bridge/routes/domains.py — domain brain management."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("bridge.routes.domains")
router = APIRouter()


@router.get("")
async def list_domains() -> dict:
    """List all configured domains and their current status."""
    from fleetwright.bridge.domain_registry import list_all, get_domain_names
    names = get_domain_names()
    active = list_all()
    return {
        "domains": [
            {
                "name": name,
                "active": name in active,
                "sid": active.get(name, {}).get("sid"),
                "started_at": active.get(name, {}).get("started_at"),
            }
            for name in names
        ]
    }


@router.post("/{name}/spawn")
async def spawn_domain(name: str) -> dict:
    """Spawn a domain brain session."""
    from fleetwright.bridge.domain_registry import get_domain_config, register
    config = get_domain_config(name)
    if not config:
        raise HTTPException(status_code=404, detail=f"domain {name!r} not configured")

    cwd = str(config.get("cwd", "~")).replace("~", str(__import__("pathlib").Path.home()))
    try:
        from fleetwright.bridge.pty_manager import spawn_session
        sid = await spawn_session(
            name=f"domain-{name}",
            cwd=cwd,
            domain=name,
            model=config.get("model"),
        )
        # The cc_session_id = sid on first spawn (bridge uses --resume for later ones)
        register(name, sid, sid, cwd)
        return {"name": name, "sid": sid, "status": "spawned"}
    except ImportError:
        raise HTTPException(status_code=501, detail="PTY manager not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{name}")
async def clear_domain(name: str) -> dict:
    """Remove a domain's registration (does not kill the PTY)."""
    from fleetwright.bridge.domain_registry import clear
    clear(name)
    return {"cleared": name}
