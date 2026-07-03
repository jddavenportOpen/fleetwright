"""fleetwright/sdk/ask_agent.py — inter-agent messaging.

Any agent can query any other agent by name and get a text response.

Under the hood, this uses the bridge's /api/sessions turn endpoint — the same
path the cockpit UI uses. It builds a fresh context-per-call so it does NOT
share memory with a live cockpit brain for that domain.

Usage:
    from fleetwright.sdk.ask_agent import ask
    response = ask("work", "What tasks are overdue this week?")
    response = ask("ceo", "Should we prioritize project A or project B this sprint?")

CLI:
    python3 -m fleetwright.sdk.ask_agent work "What tasks are overdue?"
    python3 -m fleetwright.sdk.ask_agent ceo "Review my plan"

Targets:
    - Any domain name listed in config/domains.yaml (e.g. "work", "personal")
    - "ceo"   — the CEO orchestrator session
    - "fleet" — query the fleet status

BRIDGE_URL defaults to http://127.0.0.1:8787. Set BRIDGE_URL env to override.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

BRIDGE_URL = os.environ.get("BRIDGE_URL", "http://127.0.0.1:8787")
BRIDGE_SECRET = os.environ.get("BRIDGE_SECRET", "")
ASK_TIMEOUT_SEC = int(os.environ.get("ASK_AGENT_TIMEOUT_SEC", "120"))


def ask(
    target: str,
    question: str,
    caller: str = "sdk",
    timeout: int = ASK_TIMEOUT_SEC,
) -> str:
    """Send a question to a named agent via the bridge. Returns the text response.

    Args:
        target:   domain name (from domains.yaml), "ceo", or "fleet".
        question: the text to send.
        caller:   the calling agent's name (for logging/routing).
        timeout:  max seconds to wait for a response.

    Returns:
        The agent's text response.

    Raises:
        RuntimeError: if the bridge is unreachable or returns an error.
    """
    import httpx

    thread_id = str(uuid.uuid4())
    headers = {"X-Caller": caller}
    if BRIDGE_SECRET:
        headers["Authorization"] = f"Bearer {BRIDGE_SECRET}"

    # Build a minimal turn request
    body = {
        "message": question,
        "context": {
            "caller": caller,
            "target": target,
            "thread_id": thread_id,
        },
    }

    # Try to find or create a session for this target
    try:
        with httpx.Client(base_url=BRIDGE_URL, headers=headers, timeout=timeout) as client:
            # Look up the domain's active session
            domains_resp = client.get("/api/domains")
            domains_resp.raise_for_status()
            domains = {d["name"]: d for d in domains_resp.json().get("domains", [])}

            if target in domains and domains[target].get("active"):
                sid = domains[target]["sid"]
            elif target == "ceo":
                # CEO has its own session; look in sessions list
                sessions_resp = client.get("/api/sessions")
                sessions_resp.raise_for_status()
                sessions = sessions_resp.json().get("sessions", [])
                ceo = next((s for s in sessions if "ceo" in s.get("name", "")), None)
                if not ceo:
                    raise RuntimeError("CEO session not found; start it with `fleetwright-bridge`")
                sid = ceo["sid"]
            else:
                raise RuntimeError(
                    f"target {target!r} not found or not active; "
                    f"available: {sorted(domains.keys())}"
                )

            # Send the turn
            turn_resp = client.post(
                f"/api/sessions/{sid}/turn",
                json=body,
                headers={"Accept": "text/event-stream"},
            )
            turn_resp.raise_for_status()
            return _extract_text(turn_resp.text)

    except __import__("httpx").ConnectError:
        raise RuntimeError(
            f"bridge not reachable at {BRIDGE_URL} — "
            "start it with `fleetwright-bridge` or set BRIDGE_URL"
        )


def _extract_text(sse_body: str) -> str:
    """Extract the text payload from an SSE stream response."""
    texts = []
    for line in sse_body.splitlines():
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload == "[DONE]":
                break
            try:
                data = json.loads(payload)
                if data.get("type") == "text":
                    texts.append(data.get("text", ""))
                elif data.get("type") == "result":
                    texts.append(data.get("result", ""))
            except (json.JSONDecodeError, TypeError):
                texts.append(payload)
    return "".join(texts)


def _main(argv: Optional[list[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        prog="python3 -m fleetwright.sdk.ask_agent",
        description="Ask any agent a question via the bridge.",
    )
    p.add_argument("target", help="domain name, 'ceo', etc.")
    p.add_argument("question", help="question to ask")
    p.add_argument("--caller", default="cli")
    p.add_argument("--timeout", type=int, default=ASK_TIMEOUT_SEC)
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    try:
        response = ask(args.target, args.question, caller=args.caller, timeout=args.timeout)
        print(response)
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_main())
