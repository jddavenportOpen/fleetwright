"""fleetwright/bridge/routes/agents.py — agent invocation via bridge."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("bridge.routes.agents")
router = APIRouter()


class AgentRequest(BaseModel):
    agent: str
    prompt: str
    files: list[str] = []


@router.get("")
async def list_agents() -> dict:
    """List configured agents."""
    from fleetwright.bridge.config import AGENT_COMMANDS
    return {"agents": list(AGENT_COMMANDS.keys())}


@router.post("/run")
async def run_agent(req: AgentRequest) -> dict:
    """Invoke an agent by name with a prompt."""
    from fleetwright.bridge.config import AGENT_COMMANDS
    if req.agent not in AGENT_COMMANDS:
        raise HTTPException(
            status_code=404,
            detail=f"agent {req.agent!r} not found; available: {sorted(AGENT_COMMANDS)}"
        )
    argv = AGENT_COMMANDS[req.agent](req.prompt, req.files)
    return {"argv": argv, "note": "implement subprocess invocation in pty_manager"}
