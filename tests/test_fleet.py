"""Tests for fleet.py — mocked at the subprocess/tmux level."""
import json
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fleetwright.fleet.fleet import (
    Fleet,
    FleetCapacityError,
    FleetSafetyError,
    RunHandle,
    TMUX_PREFIX,
    _assert_safe_worktree,
    _assert_safe_session,
    WORKTREE_ROOT,
)


@pytest.fixture
def mock_subprocess(monkeypatch):
    """Monkeypatch _run so no real git/tmux processes are spawned."""
    calls = []

    def fake_run(argv, *, check=True, cwd=None):
        calls.append(argv)
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    monkeypatch.setattr("fleetwright.fleet.fleet._run", fake_run)
    return calls


@pytest.fixture
def tmp_fleet(tmp_path, monkeypatch):
    """Fleet instance with all paths redirected to tmp_path."""
    monkeypatch.setenv("FLEET_WORKTREE_ROOT", str(tmp_path / "worktrees"))
    monkeypatch.setenv("FLEET_RUN_LOG_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("FLEET_GIT_ROOT", str(tmp_path))

    # Reload the module-level globals after setting env vars
    import importlib
    import fleetwright.fleet.fleet as fleet_mod
    monkeypatch.setattr(fleet_mod, "WORKTREE_ROOT", tmp_path / "worktrees")
    monkeypatch.setattr(fleet_mod, "RUN_LOG_DIR", tmp_path / "runs")
    monkeypatch.setattr(fleet_mod, "FLEET_GIT_ROOT", tmp_path)

    (tmp_path / "worktrees").mkdir(parents=True, exist_ok=True)
    (tmp_path / "runs").mkdir(parents=True, exist_ok=True)

    return Fleet(max_concurrency=3)


class TestSafetyGuards:
    def test_assert_safe_worktree_inside(self, tmp_path, monkeypatch):
        monkeypatch.setattr("fleetwright.fleet.fleet.WORKTREE_ROOT", tmp_path)
        sub = tmp_path / "abc123"
        sub.mkdir()
        _assert_safe_worktree(sub)  # should not raise

    def test_assert_safe_worktree_outside(self, tmp_path, monkeypatch):
        monkeypatch.setattr("fleetwright.fleet.fleet.WORKTREE_ROOT", tmp_path / "worktrees")
        with pytest.raises(FleetSafetyError):
            _assert_safe_worktree(Path("/tmp/evil"))

    def test_assert_safe_session_valid(self):
        _assert_safe_session("fleet-abc123")  # should not raise

    def test_assert_safe_session_invalid(self):
        with pytest.raises(FleetSafetyError):
            _assert_safe_session("hacked-session")


class TestFleetCapacity:
    def test_capacity_respected(self, tmp_fleet, mock_subprocess, monkeypatch):
        """Fleet raises FleetCapacityError when at capacity."""
        # Fake 3 active runs
        run_ids = [str(uuid.uuid4()) for _ in range(3)]
        fake_handles = [
            RunHandle(
                run_id=rid,
                agent="worker",
                objective="task",
                worktree_path=str(WORKTREE_ROOT / rid),
                tmux_session=f"{TMUX_PREFIX}{rid}",
            )
            for rid in run_ids
        ]
        monkeypatch.setattr(tmp_fleet, "list_active", lambda: fake_handles)
        with pytest.raises(FleetCapacityError):
            tmp_fleet.spawn("worker", "new task")

    def test_spawn_at_capacity_boundary(self, tmp_fleet, mock_subprocess, monkeypatch):
        """Spawn succeeds when just under capacity."""
        monkeypatch.setattr(tmp_fleet, "list_active", lambda: [])
        # Patch _tmux_session_pid to return None
        monkeypatch.setattr("fleetwright.fleet.fleet._tmux_session_pid", lambda _: None)
        handle = tmp_fleet.spawn("worker", "my task")
        assert handle.run_id
        assert handle.status == "running"


class TestFleetSpawn:
    def test_spawn_creates_workplan(self, tmp_fleet, mock_subprocess, tmp_path, monkeypatch):
        """Spawn writes a WORKPLAN.md in the worktree."""
        wt_root = tmp_path / "worktrees"
        monkeypatch.setattr("fleetwright.fleet.fleet.WORKTREE_ROOT", wt_root)
        monkeypatch.setattr(tmp_fleet, "list_active", lambda: [])
        monkeypatch.setattr("fleetwright.fleet.fleet._tmux_session_pid", lambda _: None)

        handle = tmp_fleet.spawn("researcher", "investigate LLM frameworks")

        # WORKPLAN.md should have been written
        plan = wt_root / handle.run_id / "WORKPLAN.md"
        assert plan.exists()
        content = plan.read_text()
        assert "researcher" in content
        assert "investigate LLM frameworks" in content

    def test_spawn_returns_handle(self, tmp_fleet, mock_subprocess, monkeypatch):
        monkeypatch.setattr(tmp_fleet, "list_active", lambda: [])
        monkeypatch.setattr("fleetwright.fleet.fleet._tmux_session_pid", lambda _: 42)

        handle = tmp_fleet.spawn("analyst", "analyze quarterly data")
        assert isinstance(handle, RunHandle)
        assert handle.agent == "analyst"
        assert handle.objective == "analyze quarterly data"
        assert handle.tmux_session.startswith(TMUX_PREFIX)


class TestFleetList:
    def test_list_active_empty(self, tmp_fleet, mock_subprocess, monkeypatch):
        monkeypatch.setattr("fleetwright.fleet.fleet._tmux_list_fleet_sessions", lambda: [])
        result = tmp_fleet.list_active()
        assert result == []

    def test_list_active_parses_workplan(self, tmp_fleet, tmp_path, monkeypatch):
        wt_root = tmp_path / "worktrees"
        monkeypatch.setattr("fleetwright.fleet.fleet.WORKTREE_ROOT", wt_root)
        run_id = "abc123def456"
        wt = wt_root / run_id
        wt.mkdir(parents=True, exist_ok=True)
        (wt / "WORKPLAN.md").write_text(
            f"# WORKPLAN\n\n**Agent:** analyst\n\n## Objective\n\ndo the thing\n"
        )
        session = f"{TMUX_PREFIX}{run_id}"
        monkeypatch.setattr("fleetwright.fleet.fleet._tmux_list_fleet_sessions", lambda: [session])
        monkeypatch.setattr("fleetwright.fleet.fleet._tmux_session_pid", lambda _: 99)

        handles = tmp_fleet.list_active()
        assert len(handles) == 1
        assert handles[0].agent == "analyst"
        assert handles[0].run_id == run_id


class TestFleetReap:
    def test_reap_old_dead_worktree(self, tmp_fleet, tmp_path, monkeypatch):
        wt_root = tmp_path / "worktrees"
        monkeypatch.setattr("fleetwright.fleet.fleet.WORKTREE_ROOT", wt_root)
        wt_root.mkdir(parents=True, exist_ok=True)

        run_id = str(uuid.uuid4())
        wt = wt_root / run_id
        wt.mkdir()
        # Make it appear old (set mtime to 48h ago)
        import os
        old_mtime = time.time() - 48 * 3600
        os.utime(wt, (old_mtime, old_mtime))

        monkeypatch.setattr("fleetwright.fleet.fleet._tmux_list_fleet_sessions", lambda: [])
        monkeypatch.setattr("fleetwright.fleet.fleet._run", lambda *a, **kw: MagicMock(returncode=0, stdout="", stderr=""))

        n = tmp_fleet.reap()
        assert n == 1

    def test_reap_skips_live_sessions(self, tmp_fleet, tmp_path, monkeypatch):
        wt_root = tmp_path / "worktrees"
        monkeypatch.setattr("fleetwright.fleet.fleet.WORKTREE_ROOT", wt_root)
        wt_root.mkdir(parents=True, exist_ok=True)

        run_id = str(uuid.uuid4())
        wt = wt_root / run_id
        wt.mkdir()

        session = f"{TMUX_PREFIX}{run_id}"
        monkeypatch.setattr("fleetwright.fleet.fleet._tmux_list_fleet_sessions", lambda: [session])

        n = tmp_fleet.reap()
        assert n == 0
