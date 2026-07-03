"""Tests for the checkpoints DB adapter (SQLite backend)."""
import json
import tempfile
import uuid
from pathlib import Path

import pytest

from fleetwright.fleet.checkpoints import SQLiteAdapter, Run, _row_to_run, reset_adapter


@pytest.fixture
def db(tmp_path):
    adapter = SQLiteAdapter(tmp_path / "test.db")
    yield adapter


def test_create_and_fetch(db):
    run_id = str(uuid.uuid4())
    db.create_run(run_id, "test-agent", "do something")
    row = db.fetch_row(run_id)
    assert row is not None
    assert row["run_id"] == run_id
    assert row["agent"] == "test-agent"
    assert row["status"] == "planning"


def test_update_status(db):
    run_id = str(uuid.uuid4())
    db.create_run(run_id, "worker", "task")
    db.update_status(run_id, "running")
    row = db.fetch_row(run_id)
    assert row["status"] == "running"


def test_update_status_invalid(db):
    run_id = str(uuid.uuid4())
    db.create_run(run_id, "worker", "task")
    db.update_status(run_id, "INVALID_STATUS")  # should not raise
    row = db.fetch_row(run_id)
    assert row["status"] == "planning"  # unchanged


def test_checkpoint_and_resume(db):
    run_id = str(uuid.uuid4())
    db.create_run(run_id, "orch", "research topic X")
    db.checkpoint(run_id, 1, {"step": "plan", "tasks": ["a", "b"]})
    db.checkpoint(run_id, 2, {"step": "fanout", "run_ids": ["r1", "r2"]})
    step, state = db.resume(run_id)
    assert step == 2
    assert state["step"] == "fanout"


def test_list_active(db):
    run_ids = [str(uuid.uuid4()) for _ in range(3)]
    for rid in run_ids:
        db.create_run(rid, "worker", f"task {rid[:8]}")
    db.update_status(run_ids[0], "done")  # this one should not appear
    active = db.list_active()
    active_ids = {r.run_id for r in active}
    assert run_ids[1] in active_ids
    assert run_ids[2] in active_ids
    assert run_ids[0] not in active_ids


def test_record_cost(db):
    run_id = str(uuid.uuid4())
    db.create_run(run_id, "worker", "task")
    db.record_cost(run_id, tokens_in=1000, tokens_out=500, cost_usd=0.01)
    db.record_cost(run_id, tokens_in=2000, tokens_out=300, cost_usd=0.02)
    row = db.fetch_row(run_id)
    assert row["tokens_input"] == 3000
    assert row["tokens_output"] == 800
    assert abs(row["cost_usd_total"] - 0.03) < 1e-9


def test_resume_empty(db):
    run_id = str(uuid.uuid4())
    db.create_run(run_id, "worker", "task")
    step, state = db.resume(run_id)
    assert step == 0
    assert state == {}


def test_row_to_run():
    row = {
        "run_id": "abc",
        "agent": "worker",
        "objective": "do stuff",
        "status": "running",
        "parent_run_id": None,
        "checkpoint_json": '{"1": {"step": "a"}}',
        "cost_usd_total": 0.05,
        "tokens_input": 100,
        "tokens_output": 50,
        "started_at": "2026-01-01T00:00:00+00:00",
        "updated_at": None,
        "error": None,
    }
    run = _row_to_run(row)
    assert isinstance(run, Run)
    assert run.run_id == "abc"
    assert run.cost_usd_total == 0.05
    assert run.checkpoint_json == {"1": {"step": "a"}}


def test_sqlite_adapter_with_module_api(tmp_path):
    """Test the public module-level API with a fresh SQLite adapter."""
    from fleetwright.fleet import checkpoints
    test_adapter = SQLiteAdapter(tmp_path / "module_test.db")
    reset_adapter(test_adapter)
    try:
        run_id = str(uuid.uuid4())
        checkpoints.create_run(run_id, "orch", "test objective")
        checkpoints.update_status(run_id, "running")
        checkpoints.checkpoint(run_id, 1, {"data": "test"})
        step, state = checkpoints.resume(run_id)
        assert step == 1
        assert state["data"] == "test"
        active = checkpoints.list_active()
        assert any(r.run_id == run_id for r in active)
    finally:
        reset_adapter(None)
