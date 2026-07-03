"""fleetwright/sdk/errors.py — helpers for visible error swallowing.

When a handler deliberately swallows an exception (best-effort side channels,
cache writes, telemetry), it MUST still leave a trace in the log.

Usage:
    import logging
    from fleetwright.sdk.errors import log_swallow

    logger = logging.getLogger(__name__)
    try:
        best_effort_thing()
    except Exception as exc:
        log_swallow(logger, exc, "best_effort_thing during sync")
"""
from __future__ import annotations

import logging
from typing import Optional


def log_swallow(
    logger: Optional[logging.Logger],
    exc: BaseException,
    context: str = "",
) -> None:
    """Log exc at WARNING and swallow it. Never raises."""
    msg = f"{context}: {type(exc).__name__}: {exc}" if context else f"{type(exc).__name__}: {exc}"
    if logger is not None:
        logger.warning("swallowed: %s", msg)
    else:
        logging.getLogger(__name__).warning("swallowed: %s", msg)


__all__ = ["log_swallow"]
