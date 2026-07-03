# Bridge API Reference

The Fleetwright bridge exposes a REST + SSE API at `http://localhost:8787` (configurable).

**Auth:** All endpoints (except `/health`) require `Authorization: Bearer <BRIDGE_SECRET>` when `DEV_MODE=false`.

---

## Health

### `GET /health`

Returns bridge status and version.

**Response:**
```json
{
  "status": "ok",
  "version": "0.2.0",
  "claude_binary": "/opt/homebrew/bin/claude",
  "claude_available": true,
  "db_backend": "sqlite"
}
```

### `GET /api/config`

Returns runtime configuration values.

**Response:**
```json
{
  "host": "127.0.0.1",
  "port": 8787,
  "dev_mode": false,
  "spawn_permission_mode": "auto",
  "session_idle_timeout_sec": 3600
}
```

---

## Sessions

### `GET /api/sessions`

List all active Claude Code sessions.

**Response:**
```json
{
  "sessions": [
    {
      "sid": "uuid",
      "name": "ceo",
      "domain": "ceo",
      "model": "claude-fable-5",
      "status": "idle",
      "started_at": "2026-07-03T10:00:00Z"
    }
  ]
}
```

### `POST /api/sessions`

Spawn a new Claude Code session.

**Request:**
```json
{
  "name": "my-session",
  "domain": "work",
  "cwd": "/path/to/working/dir",
  "model": "agent"
}
```

**Response:** `201`
```json
{
  "sid": "uuid",
  "name": "my-session",
  "status": "starting"
}
```

### `DELETE /api/sessions/{sid}`

Kill a session.

**Response:** `204`

### `POST /api/sessions/{sid}/turn`

Send a message and stream the response via SSE.

**Request:**
```json
{
  "message": "What tasks are overdue this week?",
  "context": {
    "caller": "sdk",
    "thread_id": "uuid"
  }
}
```

**Headers:** `Accept: text/event-stream`

**SSE stream:**
```
data: {"type": "text", "text": "Here are the overdue tasks..."}

data: {"type": "text", "text": " — Project A (2 days)"}

data: {"type": "result", "result": "Full response here"}

data: [DONE]
```

Event types:

| Type | Description |
|---|---|
| `text` | Incremental text chunk |
| `result` | Full final response |
| `tool_use` | Agent is calling a tool |
| `tool_result` | Tool call result |
| `error` | Error event |

### `POST /api/sessions/{sid}/resume`

Resume a session after a disconnect (reattaches to the existing PTY).

**Response:**
```json
{
  "sid": "uuid",
  "resumed": true
}
```

---

## Fleet

### `GET /api/fleet/sessions`

List active fleet runs.

**Response:**
```json
{
  "runs": [
    {
      "run_id": "uuid",
      "agent": "work",
      "objective": "Research topic X and write a summary",
      "status": "running",
      "worktree_path": "/path/to/worktree",
      "tmux_session": "fleet-uuid",
      "pid": 12345,
      "cost_usd_total": 0.0042,
      "started_at": "2026-07-03T10:00:00Z"
    }
  ]
}
```

### `POST /api/fleet/spawn`

Spawn a single fleet run.

**Request:**
```json
{
  "agent": "work",
  "objective": "Research topic X and write a summary",
  "parent_run_id": null
}
```

**Response:** `201`
```json
{
  "run_id": "uuid",
  "agent": "work",
  "objective": "Research topic X",
  "worktree_path": "/path/to/worktree",
  "tmux_session": "fleet-uuid",
  "status": "running"
}
```

### `POST /api/fleet/multitask`

Fan out N parallel fleet runs and wait for all to complete.

**Request:**
```json
{
  "tasks": [
    {"agent": "work", "objective": "Task 1"},
    {"agent": "work", "objective": "Task 2"},
    {"agent": "research", "objective": "Task 3"}
  ],
  "timeout_sec": 300
}
```

**Response:** `200` (after all tasks complete or timeout)
```json
{
  "results": [
    {"run_id": "uuid1", "status": "done", "cost_usd_total": 0.01},
    {"run_id": "uuid2", "status": "done", "cost_usd_total": 0.008},
    {"run_id": "uuid3", "status": "failed", "error": "..."}
  ]
}
```

### `DELETE /api/fleet/sessions/{run_id}`

Cancel a fleet run (SIGTERM the tmux session).

**Response:**
```json
{
  "cancelled": true,
  "run_id": "uuid"
}
```

---

## Domains

### `GET /api/domains`

List configured domains and their session status.

**Response:**
```json
{
  "domains": [
    {
      "name": "work",
      "description": "Primary work domain",
      "active": true,
      "sid": "uuid",
      "started_at": "2026-07-03T08:00:00Z"
    },
    {
      "name": "personal",
      "description": "Personal domain",
      "active": false,
      "sid": null,
      "started_at": null
    }
  ]
}
```

### `POST /api/domains/{name}/spawn`

Start a domain brain session.

**Response:** `201`
```json
{
  "sid": "uuid",
  "name": "work",
  "status": "starting"
}
```

---

## Agents

### `GET /api/agents`

Return the full agent registry (`agents/registry.json`).

**Response:**
```json
{
  "version": "1",
  "agents": [
    {
      "name": "ceo",
      "kind": "orchestrator",
      "description": "CEO orchestrator",
      "model": "flagship",
      "definition": "agents/examples/ceo/CLAUDE.md",
      "scope": "global"
    }
  ]
}
```

---

## Error responses

All errors follow this format:

```json
{
  "detail": "Human-readable error message"
}
```

| Status | Meaning |
|---|---|
| `400` | Bad request — invalid parameters |
| `401` | Unauthorized — missing or invalid `BRIDGE_SECRET` |
| `404` | Not found — session or run ID doesn't exist |
| `409` | Conflict — session already exists, fleet at capacity |
| `500` | Internal error — check bridge logs |
