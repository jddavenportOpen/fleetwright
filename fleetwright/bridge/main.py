"""fleetwright/bridge/main.py — FastAPI bridge server.

Wraps Claude Code PTYs and provides the REST + SSE API consumed by the cockpit.

Key endpoints:
  POST /api/sessions                    — spawn a new Claude Code session
  GET  /api/sessions                    — list active sessions
  DELETE /api/sessions/{sid}            — kill a session
  POST /api/sessions/{sid}/turn         — send a message, stream the response (SSE)
  POST /api/sessions/{sid}/resume       — resume a session after disconnect
  GET  /api/fleet/sessions              — list fleet runs
  POST /api/fleet/spawn                 — spawn a fleet run
  POST /api/fleet/multitask             — fanout N parallel fleet runs
  GET  /api/domains                     — list configured domains
  POST /api/domains/{name}/spawn        — spawn a domain brain session

Usage:
    python3 -m fleetwright.bridge.main
    # or via the CLI entry point:
    fleetwright-bridge
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger("bridge")

# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Fleetwright Bridge",
    description="PTY bridge connecting the cockpit to Claude Code sessions",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # narrow in production via CORS_ORIGINS env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Route registration ─────────────────────────────────────────────────────
from fleetwright.bridge.routes import fleet as fleet_routes
from fleetwright.bridge.routes import sessions as session_routes
from fleetwright.bridge.routes import agents as agent_routes
from fleetwright.bridge.routes import domains as domain_routes

app.include_router(fleet_routes.router,   prefix="/api/fleet",    tags=["fleet"])
app.include_router(session_routes.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(agent_routes.router,   prefix="/api/agents",   tags=["agents"])
app.include_router(domain_routes.router,  prefix="/api/domains",  tags=["domains"])


@app.get("/health")
async def health() -> dict:
    from fleetwright.bridge.config import claude_binary
    import os
    import pathlib
    claude_path = claude_binary()
    if claude_path != "claude":
        claude_available = pathlib.Path(claude_path).exists()
    else:
        import shutil
        claude_available = shutil.which("claude") is not None
    return {
        "status": "ok",
        "version": "0.2.0",
        "claude_binary": claude_path,
        "claude_available": claude_available,
        "db_backend": os.environ.get("DB_BACKEND", "sqlite"),
    }


@app.get("/api/config")
async def get_config() -> dict:
    from fleetwright.bridge import config as cfg
    return {
        "host": cfg.HOST,
        "port": cfg.PORT,
        "dev_mode": cfg.DEV_MODE,
        "spawn_permission_mode": cfg.spawn_permission_mode(),
        "session_idle_timeout_sec": cfg.SESSION_IDLE_TIMEOUT_SEC,
    }


# ── CLI entry point ────────────────────────────────────────────────────────
def _main(argv: list[str] | None = None) -> int:
    import argparse
    import uvicorn

    p = argparse.ArgumentParser(prog="fleetwright-bridge", description="Fleetwright bridge server")
    p.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8787")))
    p.add_argument("--reload", action="store_true", help="hot-reload on code change")
    p.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])
    args = p.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    log.info("starting Fleetwright bridge on %s:%d", args.host, args.port)
    uvicorn.run(
        "fleetwright.bridge.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )
    return 0


if __name__ == "__main__":
    sys.exit(_main())
