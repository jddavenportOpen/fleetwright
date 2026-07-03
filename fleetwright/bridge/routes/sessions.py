"""fleetwright/bridge/routes/sessions.py — PTY session management.

This module provides the REST + SSE API for managing Claude Code PTY sessions.
The heavy PTY machinery (pty_manager, persistent_supervisor, crash_recovery) is
imported lazily — the bridge can boot without them for testing.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("bridge.routes.sessions")
router = APIRouter()


class SpawnRequest(BaseModel):
    name: Optional[str] = None
    cwd: Optional[str] = None
    domain: Optional[str] = None
    model: Optional[str] = None
    permission_mode: Optional[str] = None
    add_dirs: list[str] = []
    env: dict[str, str] = {}


class TurnRequest(BaseModel):
    message: str
    max_duration_sec: Optional[int] = None


@router.get("")
async def list_sessions() -> dict:
    """List all active PTY sessions."""
    try:
        from fleetwright.bridge.pty_manager import list_sessions
        return {"sessions": list_sessions()}
    except ImportError:
        return {"sessions": [], "note": "pty_manager not available"}
    except Exception as e:
        log.warning("list_sessions failed: %s", e)
        return {"sessions": [], "error": str(e)}


@router.post("")
async def spawn_session(req: SpawnRequest) -> dict:
    """Spawn a new Claude Code PTY session."""
    try:
        from fleetwright.bridge.pty_manager import spawn_session as _spawn
        sid = await _spawn(
            name=req.name,
            cwd=req.cwd,
            domain=req.domain,
            model=req.model,
            permission_mode=req.permission_mode,
            add_dirs=req.add_dirs,
            env=req.env,
        )
        return {"sid": sid, "status": "spawned"}
    except ImportError:
        raise HTTPException(status_code=501, detail="PTY manager not available in this install")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{sid}")
async def kill_session(sid: str) -> dict:
    """Kill a session."""
    try:
        from fleetwright.bridge.pty_manager import kill_session
        await kill_session(sid)
        return {"killed": True, "sid": sid}
    except ImportError:
        raise HTTPException(status_code=501, detail="PTY manager not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{sid}/resume")
async def resume_session(sid: str) -> dict:
    """Resume a session that lost its PTY."""
    try:
        from fleetwright.bridge.pty_manager import resume_session
        new_sid = await resume_session(sid)
        return {"sid": new_sid, "status": "resumed"}
    except ImportError:
        raise HTTPException(status_code=501, detail="PTY manager not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


import json as _json


@router.post("/{sid}/turn")
async def session_turn(sid: str, req: TurnRequest):
    """Send a message to a session and stream the response as SSE."""
    from fastapi.responses import StreamingResponse
    from fleetwright.bridge.pty_manager import send_turn as _send_turn

    async def _generate():
        try:
            async for chunk in _send_turn(
                sid,
                req.message,
                req.max_duration_sec or 21600,
            ):
                yield chunk
        except KeyError as e:
            yield f"data: {_json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        except RuntimeError as e:
            yield f"data: {_json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        except Exception as e:
            log.exception("session_turn error: %s", e)
            yield f"data: {_json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
