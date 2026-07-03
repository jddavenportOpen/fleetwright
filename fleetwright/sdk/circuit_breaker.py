"""fleetwright/sdk/circuit_breaker.py — auth-failure circuit breaker for crons.

State machine (per named breaker):

    CLOSED    — normal; auth failures increment a counter; `threshold`
                consecutive trips it OPEN.
    OPEN      — tripped; `should_run()` returns False until `cooldown` seconds
                have elapsed. Exactly ONE alert fires at trip time.
    HALF_OPEN — cooldown elapsed; one trial run allowed. Success → CLOSED;
                another failure → OPEN (cooldown resets, no new alert).

State persists per breaker at:
    <STATE_DIR>/circuit-breakers/<name>.json

Typical cron integration:

    from fleetwright.sdk.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker("my-service")
    if not cb.should_run():
        sys.exit(0)
    try:
        count = do_credentialed_work()
        cb.record_success()
    except AuthError as exc:
        cb.record_auth_failure(str(exc))
        sys.exit(1)

CLI:
    python3 -m fleetwright.sdk.circuit_breaker should-run <name>   # exit 0=run 10=skip
    python3 -m fleetwright.sdk.circuit_breaker record-success <name>
    python3 -m fleetwright.sdk.circuit_breaker record-failure <name> [detail]
    python3 -m fleetwright.sdk.circuit_breaker status <name>
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Callable, Optional

from fleetwright.sdk.errors import log_swallow

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 3
DEFAULT_COOLDOWN = 3600  # 1h

SKIP_EXIT_CODE = 10  # CLI exit code: "breaker OPEN — skip work"

CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half_open"

_AUTH_PATTERNS = (
    re.compile(r"\b40[13]\b"),
    re.compile(r"\bunauthorized\b", re.I),
    re.compile(r"\bforbidden\b", re.I),
    re.compile(r"\binvalid[_ ]grant\b", re.I),
    re.compile(r"\binvalid[_ ](?:token|credentials)\b", re.I),
    re.compile(r"\b(?:token|credential)s?\s+(?:expired|revoked|invalid)\b", re.I),
    re.compile(r"\bauth(?:entication|orization)?[_ ]?(?:error|failed|failure)\b", re.I),
    re.compile(r"\bneeds[_ ]consent\b", re.I),
)


def is_auth_failure(message: str) -> bool:
    """True if message looks like a 401/403/auth-error-class failure."""
    if not message:
        return False
    return any(p.search(message) for p in _AUTH_PATTERNS)


class CircuitBreaker:
    """File-backed auth-failure circuit breaker."""

    def __init__(
        self,
        name: str,
        *,
        threshold: int = DEFAULT_THRESHOLD,
        cooldown: int = DEFAULT_COOLDOWN,
        state_dir: Optional[Path] = None,
        now: Optional[float] = None,
        alert_fn: Optional[Callable[[str], None]] = None,
    ) -> None:
        if not name or "/" in name or "\\" in name:
            raise ValueError(f"invalid breaker name: {name!r}")
        self.name = name
        self.threshold = max(1, int(threshold))
        self.cooldown = max(0, int(cooldown))
        if state_dir is None:
            from fleetwright.config import STATE_DIR
            state_dir = STATE_DIR / "circuit-breakers"
        self._state_dir = state_dir
        self._now_override = now
        self._alert_fn = alert_fn or self._default_alert
        self._state = self._load()

    def _now(self) -> float:
        return self._now_override if self._now_override is not None else time.time()

    @property
    def path(self) -> Path:
        return self._state_dir / f"{self.name}.json"

    def _load(self) -> dict:
        try:
            if self.path.exists():
                return json.loads(self.path.read_text())
        except (OSError, ValueError) as exc:
            log_swallow(logger, exc, f"loading breaker state {self.path}")
        return {
            "name": self.name,
            "state": CLOSED,
            "consecutive_failures": 0,
            "opened_at": None,
            "last_failure": None,
            "last_success_ts": None,
            "trip_count": 0,
        }

    def _save(self) -> None:
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(f".{int(self._now() * 1000)}.tmp")
            tmp.write_text(json.dumps(self._state, indent=2) + "\n")
            tmp.replace(self.path)
        except OSError as exc:
            log_swallow(logger, exc, f"saving breaker state {self.path}")

    @property
    def state(self) -> str:
        return self._state.get("state", CLOSED)

    def _seconds_since_open(self) -> Optional[float]:
        opened_at = self._state.get("opened_at")
        if opened_at is None:
            return None
        return self._now() - float(opened_at)

    def _cooldown_remaining(self) -> float:
        elapsed = self._seconds_since_open()
        if elapsed is None:
            return 0.0
        return max(0.0, self.cooldown - elapsed)

    def should_run(self) -> bool:
        """True if the caller should perform the credentialed work this run."""
        st = self.state
        if st == CLOSED:
            return True
        if st == HALF_OPEN:
            return True
        # OPEN
        if self._cooldown_remaining() <= 0:
            self._state["state"] = HALF_OPEN
            self._save()
            logger.info("breaker %s → HALF_OPEN (cooldown elapsed)", self.name)
            return True
        return False

    def record_success(self) -> None:
        """Reset to CLOSED."""
        was_tripped = self.state in (OPEN, HALF_OPEN)
        self._state["state"] = CLOSED
        self._state["consecutive_failures"] = 0
        self._state["opened_at"] = None
        self._state["last_success_ts"] = self._now()
        self._save()
        if was_tripped:
            logger.info("breaker %s recovered → CLOSED", self.name)
            self._alert_fn(
                f"[fleetwright] Circuit breaker '{self.name}' recovered — auth working again."
            )

    def record_auth_failure(self, detail: str = "") -> bool:
        """Record one auth-failure event. Returns True if this call TRIPPED it."""
        now = self._now()
        self._state["last_failure"] = {"ts": now, "detail": detail[:300]}

        if self.state == HALF_OPEN:
            self._state["state"] = OPEN
            self._state["opened_at"] = now
            self._save()
            logger.warning("breaker %s trial failed → OPEN (cooldown reset)", self.name)
            return False

        if self.state == OPEN:
            self._save()
            return False

        self._state["consecutive_failures"] = int(
            self._state.get("consecutive_failures", 0)
        ) + 1
        if self._state["consecutive_failures"] >= self.threshold:
            self._trip(now, detail)
            return True
        self._save()
        logger.warning(
            "breaker %s auth failure %d/%d (still CLOSED): %s",
            self.name, self._state["consecutive_failures"], self.threshold, detail[:120],
        )
        return False

    def _trip(self, now: float, detail: str) -> None:
        self._state["state"] = OPEN
        self._state["opened_at"] = now
        self._state["trip_count"] = int(self._state.get("trip_count", 0)) + 1
        self._save()
        logger.error(
            "breaker %s TRIPPED OPEN after %d consecutive auth failures: %s",
            self.name, self.threshold, detail[:200],
        )
        cooldown_min = round(self.cooldown / 60)
        self._alert_fn(
            f"[fleetwright] Circuit breaker '{self.name}' TRIPPED — "
            f"{self.threshold} consecutive auth failures. "
            f"Last error: {detail[:200] or 'n/a'}. "
            f"Polling muted for ~{cooldown_min} min."
        )

    def _default_alert(self, text: str) -> None:
        """Default alert: log to stderr. Override via alert_fn or subclass."""
        try:
            from fleetwright.sdk.notify import send_notification
            send_notification(text)
        except Exception as exc:
            log_swallow(logger, exc, f"sending alert for breaker {self.name}")

    def status(self) -> dict:
        """Machine-readable snapshot."""
        return {
            **self._state,
            "cooldown_remaining_s": round(self._cooldown_remaining(), 1),
            "should_run": self.should_run(),
        }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python3 -m fleetwright.sdk.circuit_breaker",
        description="Auth-failure circuit breaker for credential-dependent crons.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def _common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("name", help="breaker name")
        sp.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
        sp.add_argument("--cooldown", type=int, default=DEFAULT_COOLDOWN)

    sr = sub.add_parser("should-run", help=f"exit 0=run {SKIP_EXIT_CODE}=skip")
    _common(sr)

    rs = sub.add_parser("record-success", help="reset breaker on success")
    _common(rs)

    rf = sub.add_parser("record-failure", help="record one auth failure")
    _common(rf)
    rf.add_argument("detail", nargs="?", default="")
    rf.add_argument("--only-if-auth", action="store_true")

    st = sub.add_parser("status", help="print JSON status")
    _common(st)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _build_parser().parse_args(argv)
    cb = CircuitBreaker(args.name, threshold=args.threshold, cooldown=args.cooldown)

    if args.cmd == "should-run":
        return 0 if cb.should_run() else SKIP_EXIT_CODE
    if args.cmd == "record-success":
        cb.record_success()
        return 0
    if args.cmd == "record-failure":
        detail = args.detail or ""
        if getattr(args, "only_if_auth", False) and not is_auth_failure(detail):
            logger.info("breaker %s: detail not auth-class, ignoring", cb.name)
            return 0
        cb.record_auth_failure(detail)
        return 0
    if args.cmd == "status":
        print(json.dumps(cb.status(), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
