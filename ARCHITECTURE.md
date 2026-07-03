# Fleetwright — Architecture Lock (M1)

> **Status: LOCKED — 2026-07-03.** This document records the M1 scope and license decisions. It is the reference for M2 (extraction) and M4 (install story).

---

## License: Apache-2.0

**Decision:** Apache-2.0.

**Rationale:** Fleetwright is foundational infrastructure for an agentic orchestration layer. Apache-2.0 adds an explicit patent grant over MIT — important if the project gains commercial traction or enterprise contributors. Both are permissive; Apache-2.0 is the right call for infra. All dependencies (FastAPI, Next.js, Claude Code) are MIT/Apache-compatible.

---

## v1 Bundle: All Five Components Ship Together

All five components are confirmed for v1. They are tightly integrated: the cockpit is incoherent without the fleet engine; the Nerve Center is the supervision surface for the fleet; the CEO orchestrator needs the agent registry. Shipping a partial slice creates a worse product and a confused install story.

| # | Component | Role |
|---|-----------|------|
| a | **CEO Orchestrator** | Always-on lead agent: holds goals, plans work, routes tasks to the fleet, synthesizes results. |
| b | **Fleet Engine** | Spawn / supervise / reconcile / cost-attribute parallel runs via git-worktrees + tmux. |
| c | **`/chat` Cockpit** | PTY bridge + Next.js UI: session picker, multi-pane supervision, resume-from-dead, needs-you inbox. |
| d | **Agent Framework + Registry** | Shared SDK, domain agent pattern, persistent agent definitions, domain registry. |
| e | **Nerve Center Dashboard** | Web dashboard: tasks, projects, CRM, live org chart, run history, cost. |

---

## Core vs Optional-Plugin

### Core (always installed, required for Fleetwright to function)

- **Fleet engine** (`fleet.py`, `run_reconciler.py`, `checkpoints.py`) — the runtime everything builds on.
- **PTY bridge** (`bridge/`) — the FastAPI server that wraps Claude Code PTYs, manages sessions, and provides the REST + SSE API consumed by the cockpit.
- **`/chat` cockpit** (`src/app/chat/`, `CockpitView.tsx`) — the primary supervision UI.
- **Agent framework** (`agents/shared/` core modules, CLAUDE.md agent-def pattern) — the shared SDK agents run on.
- **Domain registry** (`bridge/domain_registry.py`, `bridge/persistent_supervisor.py`) — persists which domain brain is which and re-attaches it on restart.
- **CEO orchestrator** (`agents/shared/orchestrator.py` + the CEO agent definition) — the always-on lead; without it the fleet has no goal-holder.

### Optional Plugin (ships in box, can be disabled or replaced)

- **Nerve Center Dashboard** — the full web dashboard (`src/app/{tasks,projects,org,crm,runs,…}`). Users who want a CLI-only experience can disable it; the bridge API still works.
- **Example domain agents** — generic stand-ins (e.g., `work`, `personal`) that demo the domain agent pattern. Users replace these with their own domains.
- **MCP integrations** — health data sync, calendar, Telegram operator, iCloud IO, etc. All user-configured via `.env` / MCP config; absent if not configured.

### Install tiers (M4 will implement)

| Tier | Components | Use case |
|------|------------|----------|
| **minimal** (CLI) | Fleet engine + agent framework | Developers who just want the parallel-agent spawner |
| **full** (recommended) | All five | The intended Fleetwright experience |

---

## Module Map

Fleetwright's modules and their roles. See each module's docstring for full API docs.

### (a) CEO Orchestrator (`fleetwright/orchestrator/`)

| Module | Role |
|---|---|
| `orchestrator.py` | Formal plan/fanout/harvest/synthesize loop. Routes work to domain agents and fleet workers. |
| `plan_file.py` | Reads/writes `WORKPLAN.md` in the working directory — the agent's persistent state. |
| `agents/examples/ceo/` | Example CEO agent definition (`CLAUDE.md`). Copy to `~/.claude/agents/ceo.md` on install. |

### (b) Fleet Engine (`fleetwright/fleet/`)

| Module | Role |
|---|---|
| `fleet.py` | Worktree+tmux supervisor: spawn, list, cancel, reap parallel Claude Code workers. |
| `run_reconciler.py` | Cron-style reconciler: closes finished runs, attributes cost, GCs dead worktrees. |
| `checkpoints.py` | Checkpoint store: SQLite (default), Postgres, or Supabase adapters. |
| `event_ingest.py` | Parses `*.events.jsonl` files from fleet workers to extract cost + outcome. |
| `multitask.py` | High-level parallel-spawn helper: spawn N workers, wait for all, return results. |
| `drainer.py` | Drainer daemon: pulls tasks from a queue and spawns workers at a controlled rate. |

### (c) `/chat` Cockpit (`fleetwright/bridge/`, `cockpit/`)

| Module | Role |
|---|---|
| `bridge/main.py` | FastAPI app entrypoint. Loads domain registry, mounts all route groups. |
| `bridge/pty_manager.py` | PTY lifecycle: spawn Claude Code in a pty, stream stdin/stdout, manage session state. *(M4)* |
| `bridge/domain_registry.py` | YAML-driven domain registry: load `config/domains.yaml`, track active sessions. |
| `bridge/routes/sessions.py` | Session CRUD + SSE turn endpoint: `GET /api/sessions`, `POST /api/sessions/{sid}/turn`. |
| `bridge/routes/fleet.py` | Fleet REST API: spawn, list, cancel, status. |
| `bridge/routes/agents.py` | Agent registry endpoint: serve `agents/registry.json`. |
| `bridge/routes/domains.py` | Domain registry endpoint: list configured domains + live session status. |
| `cockpit/` | Next.js supervision UI — `/chat` route, multi-pane supervision, needs-you inbox. *(M4)* |

### (d) Agent Framework + Registry (`fleetwright/sdk/`, `agents/`)

| Module | Role |
|---|---|
| `sdk/claude_cli_client.py` | `claude -p` wrapper: one-shot LLM completion via Claude CLI. |
| `sdk/ask_agent.py` | Inter-agent messaging: query any domain agent or CEO by name via the bridge. |
| `sdk/circuit_breaker.py` | Circuit breaker: rate-limit and back-off for external calls. |
| `sdk/model_registry.py` | Model tier registry: load `config/model-registry.yaml`, resolve `"agent"` → model ID. |
| `sdk/notify.py` | Notification helper: log to stderr + optional Telegram push (via env config). |
| `sdk/errors.py` | Shared error types. |
| `agents/registry.json` | Agent registry: one entry per agent (name, kind, model tier, definition path). |
| `agents/examples/` | Example agent definitions (`CLAUDE.md` files) for CEO, work, and personal domain agents. |

### (e) Nerve Center Dashboard (optional plugin)

The full Nerve Center dashboard (tasks, projects, CRM, org chart, run history) is extracted as part of **M4** (cockpit extraction). It ships as an optional plugin: when disabled, the bridge API and fleet engine still work fully.

Planned modules:
- `cockpit/src/app/tasks/` — Task management UI
- `cockpit/src/app/projects/` — Project tracking
- `cockpit/src/app/org/` — Live agent org chart
- `cockpit/src/app/crm/` — Contact management
- `cockpit/src/app/runs/` — Fleet run history

---

## Data Flow

```
User
 │
 ▼
/chat cockpit (Next.js)
 │  SSE stream + REST
 ▼
Bridge (FastAPI + PTY manager)
 │  PTY / subprocess
 ├──► CEO Claude Code session  ──► plan / route
 │                                    │
 ├──► Domain agent session            │ orchestrator.fanout()
 │                                    │
 └──► Fleet Engine                 ◄──┘
       │  git-worktree + tmux
       ├──► Worker 1 (Claude Code)
       ├──► Worker 2 (Claude Code)
       └──► Worker N (Claude Code)
              │
              ▼
         agent_runs (Supabase / Postgres)
              │
              ▼
    Nerve Center Dashboard (tasks/projects/org/CRM)
```

**Key interfaces:**
- **Bridge ↔ Cockpit:** REST + SSE at `http://localhost:8787` (configurable). Auth via HMAC-JWT (secret in `.env`).
- **Bridge ↔ DB:** Supabase client (or Postgres via psycopg2). `checkpoints.py` + `chatdb.py`.
- **Fleet ↔ Cockpit:** `/api/fleet/*` bridge routes surfacing `fleet.py` and `run_reconciler.py`.
- **Agent ↔ Agent:** `ask_agent.py` (CLI bridge: `python3 -m fleetwright.sdk.ask_agent <target> "<msg>"`).

---

## What M2 (Extraction) Must Decide

The following are explicitly **deferred to M2** — not blocking M1:

1. **Monorepo vs separate packages:** single `fleetwright/` repo with `packages/{bridge,cockpit,sdk,fleet}` subdirectories vs separate npm/pypi packages. Recommendation: monorepo first, publish separately post-M6.
2. **DB abstraction:** swap the `supabase-py` client for an adapter (Supabase | local Postgres | SQLite-for-dev). Needed for the M4 install story.
3. **Domain agent config format:** YAML file describing domain name, working dir, CLAUDE.md path, MCP servers — replaces any hardcoded paths in `domain_registry.py` and the bridge.
4. **`/chat` route vs full Next.js app:** the cockpit is currently one route inside the 40-route Nerve Center app. Extraction options: (a) keep the monolith and leave non-core routes behind a feature flag, or (b) split cockpit into a standalone Next.js app. Option (a) is simpler for M2.

---

*Generated by M1 milestone completion, 2026-07-03.*
