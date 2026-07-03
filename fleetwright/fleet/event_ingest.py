"""fleetwright/fleet/event_ingest.py — parse stream-json events and persist them.

Parses a headless `claude -p --output-format stream-json --verbose` stdout stream
and persists normalized events to the configured DB backend.

Event kinds (from real stream-json output):
  type=system   subtype=init   → session start
  type=assistant               → text and/or tool_use blocks
  type=user                    → tool_result blocks
  type=result   subtype=success|error_*  → terminal event with cost + usage

The terminal type=result event carries total_cost_usd + usage. This is the
authoritative source for run cost.

CLI:
    python3 -m fleetwright.fleet.event_ingest ingest-file <run_id> <jsonl_path>
    python3 -m fleetwright.fleet.event_ingest tail <run_id> <jsonl_path>
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

# Overridable table name (env: FLEETWRIGHT_EVENTS_TABLE)
import os
EVENTS_TABLE = os.environ.get("FLEETWRIGHT_EVENTS_TABLE", "agent_run_events")


def _normalize_event(run_id: str, seq: int, raw: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Normalize one stream-json event dict to a storable row shape."""
    kind = raw.get("type", "unknown")
    subtype = raw.get("subtype", "")
    ts = raw.get("timestamp", "")

    base = {
        "run_id": run_id,
        "seq": seq,
        "kind": kind,
        "subtype": subtype,
        "ts": ts,
        "raw_json": json.dumps(raw, separators=(",", ":")),
        "cost_usd": None,
        "tokens_input": None,
        "tokens_output": None,
        "text": None,
        "tool_name": None,
        "tool_input": None,
        "tool_output": None,
        "is_error": False,
    }

    if kind == "result":
        cost = raw.get("total_cost_usd")
        usage = raw.get("usage") or {}
        base.update({
            "cost_usd": cost,
            "tokens_input": usage.get("input_tokens"),
            "tokens_output": usage.get("output_tokens"),
            "is_error": raw.get("is_error", False),
        })
    elif kind == "assistant":
        msg = raw.get("message") or {}
        content = msg.get("content") or []
        for block in content:
            btype = block.get("type", "")
            if btype == "text":
                base["text"] = block.get("text", "")[:2000]  # truncate long text
            elif btype == "tool_use":
                base["tool_name"] = block.get("name", "")
                base["tool_input"] = json.dumps(block.get("input", {}), separators=(",", ":"))[:1000]

    return base


def ingest_file(run_id: str, path: Path) -> int:
    """One-shot ingest of a complete JSONL file. Returns number of events ingested."""
    try:
        from fleetwright.fleet import checkpoints
        _adapter = checkpoints._get_adapter()
    except Exception:
        _adapter = None

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    seq = 0
    cost_usd = None
    tokens_in = None
    tokens_out = None
    terminal_status = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue

        row = _normalize_event(run_id, seq, raw)
        if row is None:
            continue

        # Extract cost from terminal result event
        if raw.get("type") == "result":
            cost_usd = row.get("cost_usd")
            tokens_in = row.get("tokens_input")
            tokens_out = row.get("tokens_output")
            terminal_status = "failed" if raw.get("is_error") else "done"

        seq += 1

    # Persist cost and terminal status
    if _adapter and run_id:
        try:
            if cost_usd is not None or tokens_in is not None:
                _adapter.record_cost(
                    run_id,
                    tokens_in or 0,
                    tokens_out or 0,
                    cost_usd or 0.0,
                )
            if terminal_status:
                _adapter.update_status(run_id, terminal_status)
        except Exception as e:
            log.warning("ingest_file: persist failed for %s: %s", run_id, e)

    log.info("ingest_file: %s → %d events ingested", run_id, seq)
    return seq


def tail(run_id: str, path: Path, poll_sec: float = 0.5, timeout_sec: float = 3600) -> int:
    """Tail a JSONL file until the terminal result event lands or timeout."""
    deadline = time.time() + timeout_sec
    seen_lines = 0
    while time.time() < deadline:
        if path.exists():
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines[seen_lines:]:
                line = line.strip()
                if not line:
                    continue
                seen_lines += 1
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if raw.get("type") == "result":
                    # Terminal — do a final ingest and exit
                    ingest_file(run_id, path)
                    return seen_lines
        time.sleep(poll_sec)
    log.warning("tail: timeout after %ss for run %s", timeout_sec, run_id)
    ingest_file(run_id, path)
    return seen_lines


def _main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="fleetwright.fleet.event_ingest")
    sub = p.add_subparsers(dest="cmd", required=True)

    fi = sub.add_parser("ingest-file", help="one-shot ingest of a complete JSONL")
    fi.add_argument("run_id")
    fi.add_argument("jsonl_path", type=Path)

    tl = sub.add_parser("tail", help="tail a JSONL until the result event lands")
    tl.add_argument("run_id")
    tl.add_argument("jsonl_path", type=Path)
    tl.add_argument("--timeout", type=float, default=3600)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.cmd == "ingest-file":
        n = ingest_file(args.run_id, args.jsonl_path)
        print(f"ingested {n} events from {args.jsonl_path}")
        return 0
    if args.cmd == "tail":
        n = tail(args.run_id, args.jsonl_path, timeout_sec=args.timeout)
        print(f"tailed {n} events from {args.jsonl_path}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(_main())
