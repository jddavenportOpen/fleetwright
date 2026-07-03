# Agent Authoring Guide

Fleetwright agents are Claude Code sessions with a **`CLAUDE.md` system prompt** that defines their role, responsibilities, and behavior. This guide covers how to write effective agent definitions and use the Fleetwright SDK from within an agent.

---

## What an agent definition is

Every agent in Fleetwright is a directory containing a `CLAUDE.md` file. When the bridge spawns a session for that agent, it loads the `CLAUDE.md` as the system prompt — the agent's persistent identity.

```
agents/examples/
├── ceo/
│   └── CLAUDE.md    ← CEO orchestrator definition
├── work/
│   └── CLAUDE.md    ← work domain agent definition
└── personal/
    └── CLAUDE.md    ← personal domain agent definition
```

---

## Agent definition structure

A good `CLAUDE.md` answers five questions:

1. **Who are you?** — role and purpose
2. **What do you own?** — your domain, state files, and responsibilities
3. **What can you do?** — tools, SDK calls, APIs available
4. **What don't you do?** — explicit exclusions to prevent scope creep
5. **How do you behave?** — communication style, decision rules

### Minimal example

```markdown
# My Domain Agent — Fleetwright

You are the **[domain]** agent for this Fleetwright installation.
Your role is [one sentence: what you're responsible for].

## Responsibilities

- [What you actively manage]
- [What you surface or report]
- [What you execute or delegate]

## State

Your state lives in your working directory (`cwd` in domains.yaml):
- `WORKPLAN.md` — active tasks and projects
- `state/report.md` — daily status summary

## What you have access to

- Filesystem access under your working directory
- The bridge API at `http://localhost:8787` for inter-agent messaging
- Any MCP servers configured in `.fleetwright/config/.mcp.json`

## What you don't do

- [Out-of-scope area] — route those to [other agent]
- No destructive operations without user confirmation

## Communication style

- [Tone and format preferences]
- Lead with the most important information
```

---

## SDK modules

Every agent running inside a Fleetwright session has access to the `fleetwright.sdk` package.

### `llm_call` — one-shot LLM completion

```python
from fleetwright.sdk.claude_cli_client import llm_call

summary = llm_call("Summarize: " + long_text, model="agent")
```

**Model tiers** (from `config/model-registry.yaml`):

| Tier | When to use |
|---|---|
| `flagship` | Complex reasoning, CEO-level decisions |
| `review` | Code review, analysis |
| `agent` | Standard domain agent work (default) |
| `bulk` | High-volume, cost-sensitive tasks |

### `ask_agent` — inter-agent messaging

```python
from fleetwright.sdk.ask_agent import ask

# Ask the work agent about overdue tasks
response = ask("work", "What tasks are overdue this week?", caller="ceo")

# Ask the CEO for a routing decision
response = ask("ceo", "Should I prioritize project A or B?", caller="work")
```

**CLI equivalent:**
```bash
python3 -m fleetwright.sdk.ask_agent work "What tasks are overdue?"
```

`ask()` finds the domain's active session via the bridge and sends a turn. It returns the text response. If the target domain isn't active, it raises `RuntimeError` with a clear message.

### `circuit_breaker` — rate-limit external calls

```python
from fleetwright.sdk.circuit_breaker import CircuitBreaker

cb = CircuitBreaker(max_failures=3, reset_timeout=60.0)

@cb.protect
def call_external_api(url: str) -> dict:
    ...
```

After `max_failures` consecutive failures, the breaker trips and raises `CircuitBreakerOpen` for `reset_timeout` seconds before allowing retries.

### `notify` — send alerts

```python
from fleetwright.sdk.notify import notify

notify("BLOCKED: need user input on project X")
```

Logs to stderr and (if `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` are set) pushes to Telegram.

### `model_registry` — resolve tier to model ID

```python
from fleetwright.sdk import model_registry as mr

model_id = mr.cli_id("agent")   # → "claude-sonnet-4-6" (or override)
```

---

## Lifecycle: how an agent session starts

1. User opens a domain panel in the cockpit, or the bridge auto-resumes it (if `auto_resume: true` in `domains.yaml`).
2. Bridge calls `pty_manager.spawn_session()` with the agent's `CLAUDE.md` as the system prompt.
3. Claude Code starts in the domain's `cwd` (from `domains.yaml`).
4. The agent reads its state files (`WORKPLAN.md`, `state/report.md`) and is ready for turns.

---

## Writing a heartbeat agent

A heartbeat is an agent run on a schedule to produce a status report. It should:

1. Read `WORKPLAN.md` for active tasks
2. Update `state/report.md`
3. Surface any blockers

```markdown
## Heartbeat

When invoked as a scheduled heartbeat:
1. Re-read `WORKPLAN.md` — note overdue items
2. Write a concise status update to `state/report.md`
3. If any task is blocked, call `notify("BLOCKED: ...")` and surface it
4. Keep the update under 200 words — this is a status report, not a dissertation
```

Schedule heartbeats via cron or a drainer daemon:
```bash
# Example crontab entry (runs "work" heartbeat daily at 09:00)
0 9 * * * python3 -m fleetwright.sdk.ask_agent work "Run your heartbeat." --caller scheduler
```

---

## Fleet worker agent pattern

Fleet workers are spawned for isolated tasks (code changes, research, one-off builds). They run headless via `fleet.py` and write output to `*.events.jsonl`. A fleet worker's `CLAUDE.md` should be:

- **Specific** — one clear objective, not a general-purpose brain
- **Self-contained** — reads its objective from `WORKPLAN.md` at startup
- **Completion-aware** — knows when it's done and exits cleanly

```markdown
# Research Worker — Fleetwright Fleet

You are a fleet worker. Your objective is in `WORKPLAN.md`. Read it now.

Complete the objective fully, then stop. Do not wait for further input.

Log all material decisions as you go.
```

The fleet engine automatically writes the objective into `WORKPLAN.md` before spawning, so you can read it from there.

---

## Agent registry

Every agent must have an entry in `agents/registry.json`:

```json
{
  "name": "my-agent",
  "kind": "domain",
  "description": "My domain agent — [what it does]",
  "model": "agent",
  "definition": "agents/examples/my-agent/CLAUDE.md",
  "scope": "domain"
}
```

**Fields:**

| Field | Values | Description |
|---|---|---|
| `name` | string | Unique agent name, used in `ask_agent` |
| `kind` | `orchestrator` \| `domain` \| `worker` | Agent kind |
| `model` | `flagship` \| `review` \| `agent` \| `bulk` | Model tier |
| `definition` | path | Relative path to the `CLAUDE.md` file |
| `scope` | `global` \| `domain` \| `fleet` | Scoping hint for routing |

---

## Best practices

**Be specific about state.** Tell the agent exactly which files hold its state and what each one means. Vague state descriptions lead to inconsistent behavior.

**Explicit exclusions matter.** If a domain agent should NOT handle finance (even though it's related to work), say so explicitly and name the right redirect.

**Keep heartbeats cheap.** Don't force ultracode on rote status-report runs — `model: bulk` is appropriate for heartbeats that just write a `report.md`.

**Name things consistently.** Use the same terminology in `CLAUDE.md`, `domains.yaml`, and `registry.json` — it reduces confusion when the agent routes tasks.

**Test with `ask_agent`.** You can test your agent definition without the full cockpit:
```bash
python3 -m fleetwright.sdk.ask_agent my-agent "What's your current status?"
```
