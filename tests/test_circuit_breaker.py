"""Tests for circuit_breaker.py — using injectable clock for determinism."""
import json
import tempfile
from pathlib import Path

import pytest

from fleetwright.sdk.circuit_breaker import (
    CircuitBreaker,
    CLOSED,
    OPEN,
    HALF_OPEN,
    is_auth_failure,
)


@pytest.fixture
def cb_dir(tmp_path):
    return tmp_path / "breakers"


def make_cb(name, *, now=1000.0, threshold=3, cooldown=3600, state_dir, alerts=None):
    recorded_alerts = [] if alerts is None else alerts

    def record_alert(text):
        recorded_alerts.append(text)

    return CircuitBreaker(
        name,
        threshold=threshold,
        cooldown=cooldown,
        state_dir=state_dir,
        now=now,
        alert_fn=record_alert,
    ), recorded_alerts


class TestIsAuthFailure:
    def test_401(self):
        assert is_auth_failure("HTTP Error 401: Unauthorized")

    def test_403(self):
        assert is_auth_failure("403 Forbidden")

    def test_invalid_grant(self):
        assert is_auth_failure("invalid_grant: token expired")

    def test_token_expired(self):
        assert is_auth_failure("Token expired")

    def test_auth_error(self):
        assert is_auth_failure("authentication failed")

    def test_transient_500(self):
        assert not is_auth_failure("500 Internal Server Error")

    def test_empty(self):
        assert not is_auth_failure("")


class TestCircuitBreakerClosed:
    def test_starts_closed(self, cb_dir):
        cb, _ = make_cb("test", state_dir=cb_dir)
        assert cb.state == CLOSED
        assert cb.should_run()

    def test_success_resets_counter(self, cb_dir):
        cb, _ = make_cb("test", state_dir=cb_dir, threshold=3)
        cb.record_auth_failure("err 1")
        cb.record_auth_failure("err 2")
        cb.record_success()
        # Next two failures should not trip (counter was reset)
        cb.record_auth_failure("err 3")
        cb.record_auth_failure("err 4")
        assert cb.state == CLOSED

    def test_below_threshold_stays_closed(self, cb_dir):
        cb, _ = make_cb("test", state_dir=cb_dir, threshold=3)
        cb.record_auth_failure("err 1")
        cb.record_auth_failure("err 2")
        assert cb.state == CLOSED
        assert cb.should_run()


class TestCircuitBreakerTrip:
    def test_trips_at_threshold(self, cb_dir):
        alerts = []
        cb, _ = make_cb("test", state_dir=cb_dir, threshold=3, alerts=alerts)
        cb.record_auth_failure("err 1")
        cb.record_auth_failure("err 2")
        tripped = cb.record_auth_failure("err 3")
        assert tripped
        assert cb.state == OPEN
        assert not cb.should_run()
        assert len(alerts) == 1  # exactly one alert

    def test_open_does_not_re_alert(self, cb_dir):
        alerts = []
        cb, _ = make_cb("test", state_dir=cb_dir, threshold=2, alerts=alerts)
        cb.record_auth_failure("err 1")
        cb.record_auth_failure("err 2")
        cb.record_auth_failure("err 3")  # already OPEN
        assert len(alerts) == 1  # still just one


class TestCircuitBreakerCooldown:
    def test_cooldown_blocking(self, cb_dir):
        cb, _ = make_cb("test", state_dir=cb_dir, threshold=1, cooldown=3600, now=1000.0)
        cb.record_auth_failure("err")
        assert not cb.should_run()

    def test_cooldown_elapsed_transitions_half_open(self, cb_dir):
        cb, _ = make_cb("test", state_dir=cb_dir, threshold=1, cooldown=3600, now=1000.0)
        cb.record_auth_failure("err")
        assert cb.state == OPEN

        # Advance time past cooldown
        cb._now_override = 1000.0 + 3601
        assert cb.should_run()
        assert cb.state == HALF_OPEN


class TestCircuitBreakerHalfOpen:
    def test_half_open_success_closes(self, cb_dir):
        alerts = []
        cb, _ = make_cb("test", state_dir=cb_dir, threshold=1, cooldown=60, now=0.0, alerts=alerts)
        cb.record_auth_failure("err")
        cb._now_override = 61.0
        cb.should_run()  # transitions to HALF_OPEN
        cb.record_success()
        assert cb.state == CLOSED
        assert len(alerts) == 2  # trip alert + recovery alert

    def test_half_open_failure_reopens(self, cb_dir):
        alerts = []
        cb, _ = make_cb("test", state_dir=cb_dir, threshold=1, cooldown=60, now=0.0, alerts=alerts)
        cb.record_auth_failure("err")
        cb._now_override = 61.0
        cb.should_run()  # → HALF_OPEN
        cb.record_auth_failure("trial failed")
        assert cb.state == OPEN
        assert len(alerts) == 1  # no new alert on re-trip


class TestCircuitBreakerPersistence:
    def test_state_persists_across_instances(self, cb_dir):
        cb1, _ = make_cb("persist-test", state_dir=cb_dir, threshold=2)
        cb1.record_auth_failure("err 1")
        cb1.record_auth_failure("err 2")
        assert cb1.state == OPEN

        # Load same breaker in a new instance
        cb2, _ = make_cb("persist-test", state_dir=cb_dir, threshold=2)
        assert cb2.state == OPEN

    def test_status_output(self, cb_dir):
        cb, _ = make_cb("status-test", state_dir=cb_dir)
        s = cb.status()
        assert "state" in s
        assert "should_run" in s
        assert "cooldown_remaining_s" in s


class TestCircuitBreakerCLI:
    def test_cli_should_run(self, cb_dir, monkeypatch):
        monkeypatch.setenv("FLEETWRIGHT_STATE_DIR", str(cb_dir.parent))
        from fleetwright.sdk.circuit_breaker import main
        # Fresh breaker → should return 0 (run)
        ret = main(["should-run", "cli-test", "--threshold", "3"])
        assert ret == 0

    def test_cli_status(self, cb_dir, monkeypatch, capsys):
        monkeypatch.setenv("FLEETWRIGHT_STATE_DIR", str(cb_dir.parent))
        from fleetwright.sdk.circuit_breaker import main
        ret = main(["status", "cli-status-test"])
        assert ret == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["state"] == CLOSED
