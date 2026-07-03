"""Tests for the PTY session manager (M4)."""
from __future__ import annotations

import asyncio
import pytest

from fleetwright.bridge import pty_manager as pm


@pytest.fixture(autouse=True)
def clear_sessions():
    """Reset session state between tests."""
    pm._sessions.clear()
    yield
    pm._sessions.clear()


# ── list_sessions ──────────────────────────────────────────────────────────

def test_list_sessions_empty():
    assert pm.list_sessions() == []


# ── spawn_session ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_spawn_session_returns_sid():
    sid = await pm.spawn_session(name="test", cwd="/tmp")
    assert isinstance(sid, str) and len(sid) == 36  # UUID format


@pytest.mark.asyncio
async def test_spawn_session_appears_in_list():
    sid = await pm.spawn_session(name="alpha", cwd="/tmp")
    sessions = pm.list_sessions()
    sids = [s["sid"] for s in sessions]
    assert sid in sids


@pytest.mark.asyncio
async def test_spawn_session_defaults():
    sid = await pm.spawn_session()
    sessions = pm.list_sessions()
    s = next(x for x in sessions if x["sid"] == sid)
    assert s["status"] == "idle"
    assert s["cc_session_id"] is None
    assert "session-" in s["name"]


@pytest.mark.asyncio
async def test_spawn_session_stores_name_and_domain():
    sid = await pm.spawn_session(name="work-brain", domain="work", cwd="/tmp")
    sessions = pm.list_sessions()
    s = next(x for x in sessions if x["sid"] == sid)
    assert s["name"] == "work-brain"
    assert s["domain"] == "work"


@pytest.mark.asyncio
async def test_spawn_multiple_sessions():
    ids = [await pm.spawn_session(name=f"s{i}", cwd="/tmp") for i in range(3)]
    assert len(set(ids)) == 3  # all unique
    assert len(pm.list_sessions()) == 3


# ── kill_session ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_kill_session_marks_dead():
    sid = await pm.spawn_session(name="to-kill", cwd="/tmp")
    await pm.kill_session(sid)
    sessions = pm.list_sessions()
    assert not any(s["sid"] == sid for s in sessions)  # dead sessions excluded


@pytest.mark.asyncio
async def test_kill_unknown_session_raises():
    with pytest.raises(KeyError):
        await pm.kill_session("00000000-0000-0000-0000-000000000000")


# ── resume_session ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resume_session_returns_new_sid():
    sid = await pm.spawn_session(name="resumable", cwd="/tmp")
    new_sid = await pm.resume_session(sid)
    assert new_sid != sid
    assert len(new_sid) == 36


@pytest.mark.asyncio
async def test_resume_copies_name_and_domain():
    sid = await pm.spawn_session(name="brain", domain="personal", cwd="/tmp")
    new_sid = await pm.resume_session(sid)
    sessions = pm.list_sessions()
    new_s = next(x for x in sessions if x["sid"] == new_sid)
    assert new_s["name"] == "brain"
    assert new_s["domain"] == "personal"
    assert new_s["status"] == "idle"


@pytest.mark.asyncio
async def test_resume_preserves_cc_session_id():
    sid = await pm.spawn_session(name="cc-test", cwd="/tmp")
    # Manually set a fake cc_session_id as would happen after first turn
    pm._sessions[sid].cc_session_id = "fake-claude-session-123"
    new_sid = await pm.resume_session(sid)
    new_s = pm._sessions[new_sid]
    assert new_s.cc_session_id == "fake-claude-session-123"


@pytest.mark.asyncio
async def test_resume_marks_old_session_dead():
    sid = await pm.spawn_session(name="old", cwd="/tmp")
    await pm.resume_session(sid)
    assert pm._sessions[sid].status == "dead"


# ── send_turn guards ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_turn_unknown_session_raises():
    with pytest.raises(KeyError):
        async for _ in pm.send_turn("00000000-0000-0000-0000-000000000000", "hi"):
            pass


@pytest.mark.asyncio
async def test_send_turn_dead_session_raises():
    sid = await pm.spawn_session(name="dead-test", cwd="/tmp")
    await pm.kill_session(sid)
    # The session is in _sessions with status=dead
    pm._sessions[sid]  # confirm still tracked
    with pytest.raises(RuntimeError, match="dead"):
        async for _ in pm.send_turn(sid, "hi"):
            pass


@pytest.mark.asyncio
async def test_session_busy_guard():
    sid = await pm.spawn_session(name="busy-test", cwd="/tmp")
    pm._sessions[sid].status = "busy"
    with pytest.raises(RuntimeError, match="busy"):
        async for _ in pm.send_turn(sid, "hi"):
            pass


# ── session dict keys ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_to_dict_has_all_keys():
    sid = await pm.spawn_session(name="dict-test", domain="work", cwd="/tmp", model="claude-haiku-4-5-20251001")
    sessions = pm.list_sessions()
    s = next(x for x in sessions if x["sid"] == sid)
    assert set(s.keys()) == {"sid", "name", "cwd", "domain", "model", "cc_session_id", "status", "started_at"}
    assert s["model"] == "claude-haiku-4-5-20251001"
