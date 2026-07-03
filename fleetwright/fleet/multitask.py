"""fleetwright/fleet/multitask.py — fanout helper for parallel fleet runs.

Wraps Fleet().spawn() to spin up N parallel Claude Code agents from a list of
objectives. Designed to be called from the bridge's /api/fleet/multitask endpoint
or directly from orchestrators.

Design:
  * Independent failures — if one spawn fails, others still run. Failed slots
    get an empty string "".
  * Capacity check upfront — if len(objectives) + active > max, raise before
    spawning anything (no half-fanouts).
  * Async wrapper — Fleet.spawn() is sync; wrapped in asyncio.to_thread() so
    the bridge event loop stays unblocked.

CLI smoke:
    python3 -m fleetwright.fleet.multitask "task A" "task B" "task C"
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

MAX_CONCURRENCY = int(__import__("os").environ.get("FLEET_MAX_PARALLEL", "10"))


class MultitaskError(Exception):
    """Base error for multitask failures."""


class FleetCapacityError(MultitaskError):
    """Raised when the requested fanout would exceed the fleet cap."""


def _try_import_fleet():
    try:
        from fleetwright.fleet import fleet as _fleet_mod
        upstream_cap = getattr(_fleet_mod, "FleetCapacityError", FleetCapacityError)
        return _fleet_mod.Fleet, upstream_cap
    except Exception as e:
        logger.info("Fleet not available — using fallback spawner: %s", e)
        return None, None


def _fallback_spawn(agent: str, objective: str, parent_run_id: Optional[str]) -> str:
    run_id = uuid.uuid4().hex[:12]
    logger.warning(
        "fallback spawn (no Fleet): run_id=%s agent=%s objective=%s",
        run_id, agent, objective[:80],
    )
    return run_id


async def multitask(
    objectives: list[str],
    parent_run_id: Optional[str] = None,
    agent: str = "fanout-worker",
) -> list[str]:
    """Fanout: spawn N agents in parallel via Fleet().

    Returns a list of run_ids in the same order as objectives.
    Empty string ("") for any objective whose spawn failed.

    Raises:
        ValueError: if objectives is empty or any objective is blank.
        FleetCapacityError: if the requested fanout exceeds the cap.
    """
    if not objectives:
        raise ValueError("multitask requires at least 1 objective")
    cleaned = [o.strip() for o in objectives]
    if any(not o for o in cleaned):
        raise ValueError("multitask objectives must be non-empty after strip()")

    Fleet, upstream_cap = _try_import_fleet()

    fleet_inst = None
    if Fleet is not None:
        try:
            fleet_inst = Fleet(max_concurrency=MAX_CONCURRENCY)
            active = fleet_inst.list_active()
            if len(active) + len(cleaned) > MAX_CONCURRENCY:
                raise FleetCapacityError(
                    f"fleet at {len(active)}/{MAX_CONCURRENCY}; "
                    f"cannot accept {len(cleaned)} more"
                )
        except FleetCapacityError:
            raise
        except Exception as e:
            logger.warning("Fleet.list_active() failed; falling back: %s", e)
            fleet_inst = None

    async def _spawn_one(idx: int, objective: str) -> tuple[int, str]:
        try:
            if fleet_inst is not None:
                handle = await asyncio.to_thread(
                    fleet_inst.spawn, agent, objective, parent_run_id
                )
                return idx, handle.run_id
            run_id = await asyncio.to_thread(
                _fallback_spawn, agent, objective, parent_run_id
            )
            return idx, run_id
        except Exception as e:
            if upstream_cap and isinstance(e, upstream_cap):
                logger.error("spawn[%d] capacity race for %r: %s", idx, objective[:60], e)
            else:
                logger.error("spawn[%d] failed for %r: %s", idx, objective[:60], e)
            return idx, ""

    results = await asyncio.gather(
        *[_spawn_one(i, obj) for i, obj in enumerate(cleaned)],
        return_exceptions=False,
    )
    results.sort(key=lambda t: t[0])
    return [run_id for _, run_id in results]


def _main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="fleetwright.fleet.multitask",
        description="Fanout N parallel Claude Code agents.",
    )
    p.add_argument("objectives", nargs="+", help="objective strings")
    p.add_argument("--parent", default=None, help="parent_run_id")
    p.add_argument("--agent", default="fanout-worker", help="agent label")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        ids = asyncio.run(multitask(args.objectives, args.parent, args.agent))
    except (ValueError, FleetCapacityError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    for obj, rid in zip(args.objectives, ids):
        print(f"{rid or '<failed>'}\t{obj}")
    return 0 if all(ids) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
