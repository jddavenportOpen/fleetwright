"""fleetwright/bridge/routes/fleet.py — fleet management REST API."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("bridge.routes.fleet")
router = APIRouter()


class SpawnRequest(BaseModel):
    agent: str = "worker"
    objective: str
    parent_run_id: Optional[str] = None


class MultitaskRequest(BaseModel):
    objectives: list[str]
    parent_run_id: Optional[str] = None
    agent: str = "fanout-worker"


@router.get("/sessions")
async def list_fleet_sessions() -> dict:
    """List active fleet runs."""
    try:
        from fleetwright.fleet.checkpoints import list_active
        runs = list_active()
        return {"runs": [
            {
                "run_id": r.run_id,
                "agent": r.agent,
                "status": r.status,
                "objective": r.objective[:100],
                "cost_usd_total": r.cost_usd_total,
                "started_at": r.started_at,
            }
            for r in runs
        ]}
    except Exception as e:
        log.warning("list_fleet_sessions failed: %s", e)
        return {"runs": [], "error": str(e)}


@router.post("/spawn")
async def spawn_fleet_run(req: SpawnRequest) -> dict:
    """Spawn a single fleet run."""
    try:
        from fleetwright.fleet.fleet import Fleet
        fleet = Fleet()
        handle = fleet.spawn(req.agent, req.objective, req.parent_run_id)
        return {"run_id": handle.run_id, "tmux_session": handle.tmux_session, "status": "running"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multitask")
async def multitask(req: MultitaskRequest) -> dict:
    """Fanout N parallel fleet runs."""
    try:
        from fleetwright.fleet.multitask import multitask as _multitask
        run_ids = await _multitask(req.objectives, req.parent_run_id, req.agent)
        return {
            "run_ids": run_ids,
            "spawned": sum(1 for r in run_ids if r),
            "failed": sum(1 for r in run_ids if not r),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/runs/{run_id}")
async def cancel_run(run_id: str) -> dict:
    """Cancel a fleet run."""
    try:
        from fleetwright.fleet.fleet import Fleet
        fleet = Fleet()
        ok = fleet.cancel(run_id)
        return {"cancelled": ok, "run_id": run_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reap")
async def reap_worktrees() -> dict:
    """GC dead worktrees older than 24h."""
    try:
        from fleetwright.fleet.fleet import Fleet
        fleet = Fleet()
        n = fleet.reap()
        return {"reaped": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reconcile")
async def reconcile_runs() -> dict:
    """Close lifecycle of fleet runs whose tmux session is dead."""
    try:
        from fleetwright.fleet.run_reconciler import reconcile
        summary = reconcile()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
