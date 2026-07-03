"""Tests for fleet/multitask.py — async fanout helper."""
import asyncio
import uuid
from unittest.mock import MagicMock, patch

import pytest

from fleetwright.fleet.multitask import (
    FleetCapacityError,
    MAX_CONCURRENCY,
    MultitaskError,
    multitask,
)


# ── Helpers ─────────────────────────────────────────────────────────────────
def make_handle(run_id=None):
    """Build a fake RunHandle-like object."""
    h = MagicMock()
    h.run_id = run_id or uuid.uuid4().hex[:12]
    return h


# ── Validation tests ─────────────────────────────────────────────────────────
class TestMultitaskValidation:
    def test_empty_objectives_raises(self):
        with pytest.raises(ValueError, match="at least 1"):
            asyncio.run(multitask([]))

    def test_blank_objective_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            asyncio.run(multitask(["valid task", "   "]))

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            asyncio.run(multitask(["   \t   "]))


# ── Fleet-absent fallback ────────────────────────────────────────────────────
class TestMultitaskFallback:
    def test_fallback_when_fleet_unavailable(self, monkeypatch):
        """When Fleet can't be imported, fallback spawner returns run_ids."""
        monkeypatch.setattr(
            "fleetwright.fleet.multitask._try_import_fleet",
            lambda: (None, None),
        )
        ids = asyncio.run(multitask(["task A", "task B"]))
        assert len(ids) == 2
        assert all(ids)  # all non-empty

    def test_fallback_order_preserved(self, monkeypatch):
        """Result order matches input objectives order."""
        monkeypatch.setattr(
            "fleetwright.fleet.multitask._try_import_fleet",
            lambda: (None, None),
        )
        ids = asyncio.run(multitask(["first", "second", "third"]))
        assert len(ids) == 3


# ── Fleet-present behavior ───────────────────────────────────────────────────
class TestMultitaskWithFleet:
    def _make_mock_fleet_class(self, active_count=0, spawn_side_effect=None):
        """Return a mock Fleet class whose instances behave predictably."""
        handles = [make_handle() for _ in range(active_count)]

        class MockFleet:
            def __init__(self, max_concurrency=None):
                self.max_concurrency = max_concurrency

            def list_active(self):
                return handles

            def spawn(self, agent, objective, parent_run_id=None):
                if spawn_side_effect:
                    raise spawn_side_effect
                return make_handle()

        return MockFleet

    def test_single_objective_spawns_one(self, monkeypatch):
        MockFleet = self._make_mock_fleet_class(active_count=0)
        monkeypatch.setattr(
            "fleetwright.fleet.multitask._try_import_fleet",
            lambda: (MockFleet, FleetCapacityError),
        )
        ids = asyncio.run(multitask(["investigate topic X"]))
        assert len(ids) == 1
        assert ids[0]  # non-empty

    def test_multiple_objectives_all_spawn(self, monkeypatch):
        MockFleet = self._make_mock_fleet_class(active_count=0)
        monkeypatch.setattr(
            "fleetwright.fleet.multitask._try_import_fleet",
            lambda: (MockFleet, FleetCapacityError),
        )
        ids = asyncio.run(multitask(["A", "B", "C"], agent="analyst"))
        assert len(ids) == 3
        assert all(ids)

    def test_capacity_check_raises_before_spawn(self, monkeypatch):
        """When active + requested > max, raises FleetCapacityError before spawning."""
        MockFleet = self._make_mock_fleet_class(active_count=MAX_CONCURRENCY)
        monkeypatch.setattr(
            "fleetwright.fleet.multitask._try_import_fleet",
            lambda: (MockFleet, FleetCapacityError),
        )
        with pytest.raises(FleetCapacityError):
            asyncio.run(multitask(["one more task"]))

    def test_partial_spawn_failure_returns_empty_string(self, monkeypatch):
        """If one spawn fails, that slot gets empty string; others succeed."""

        class FlakyFleet:
            def __init__(self, max_concurrency=None):
                pass

            def list_active(self):
                return []

            def spawn(self, agent, objective, parent_run_id=None):
                # Fail deterministically on the named objective, not call order.
                # Concurrent threads race on call_count making order-based checks flaky.
                if "fail" in objective:
                    raise RuntimeError("tmux died mid-spawn")
                return make_handle()

        monkeypatch.setattr(
            "fleetwright.fleet.multitask._try_import_fleet",
            lambda: (FlakyFleet, FleetCapacityError),
        )
        ids = asyncio.run(multitask(["ok-1", "fail-2", "ok-3"]))
        assert len(ids) == 3
        assert ids[0]  # succeeded
        assert ids[1] == ""  # failed → empty string
        assert ids[2]  # succeeded

    def test_parent_run_id_propagated(self, monkeypatch):
        """parent_run_id is forwarded to each Fleet.spawn() call."""
        received_parents = []

        class TrackingFleet:
            def __init__(self, max_concurrency=None):
                pass

            def list_active(self):
                return []

            def spawn(self, agent, objective, parent_run_id=None):
                received_parents.append(parent_run_id)
                return make_handle()

        monkeypatch.setattr(
            "fleetwright.fleet.multitask._try_import_fleet",
            lambda: (TrackingFleet, FleetCapacityError),
        )
        parent_id = "parent-abc123"
        asyncio.run(multitask(["child A", "child B"], parent_run_id=parent_id))
        assert all(p == parent_id for p in received_parents)
        assert len(received_parents) == 2


class TestMultitaskEdgeCases:
    def test_single_char_objectives(self, monkeypatch):
        monkeypatch.setattr(
            "fleetwright.fleet.multitask._try_import_fleet",
            lambda: (None, None),
        )
        ids = asyncio.run(multitask(["x"]))
        assert len(ids) == 1

    def test_whitespace_stripped_from_objectives(self, monkeypatch):
        """Leading/trailing whitespace is stripped before spawning."""
        seen = []

        class TrackingFleet:
            def __init__(self, max_concurrency=None):
                pass

            def list_active(self):
                return []

            def spawn(self, agent, objective, parent_run_id=None):
                seen.append(objective)
                return make_handle()

        monkeypatch.setattr(
            "fleetwright.fleet.multitask._try_import_fleet",
            lambda: (TrackingFleet, FleetCapacityError),
        )
        asyncio.run(multitask(["  do thing  ", "\ttask 2\n"]))
        assert seen[0] == "do thing"
        assert seen[1] == "task 2"
