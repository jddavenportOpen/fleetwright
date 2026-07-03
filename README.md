# Fleetwright

**Self-hosted agent operations OS — a persistent chief of staff that commands a fleet of AI agents across your whole work.**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-69%20passing-brightgreen.svg)](tests/)

---

Fleetwright gives you a **persistent, always-on agent fleet** on your own machine. A CEO orchestrator holds your goals and routes work to specialized domain agents; a Next.js cockpit lets you supervise everything from a browser; and the fleet engine can run dozens of Claude Code workers in parallel across isolated git worktrees.

```
your browser
     │  (Next.js cockpit, port 3131)
     ▼
Fleetwright Bridge  (FastAPI, port 8787)
     ├── CEO session         ← holds your goals, routes work
     ├── work domain agent   ← professional projects + tasks
     ├── personal domain     ← life admin + personal goals
     └── Fleet Engine
           ├── worker-1  (Claude Code in git worktree)
           ├── worker-2
           └── worker-N
```

---

## Why Fleetwright?

| Feature | What it gives you |
|---------|-------------------|
| **Persistent agents** | Domain brains re-attach on restart — they don't forget between sessions |
| **Fleet engine** | Spawn N Claude Code workers in parallel, each in an isolated git worktree |
| **CEO orchestrator** | One always-on lead agent that holds your goals and routes cross-domain work |
| **Supervision cockpit** | Dark-mode Next.js dashboard — sessions, fleet runs, domain status at a glance |
| **Bring your own subscription** | Uses your Claude Max subscription, not the metered API |
| **Single-machine install** | One command, no cloud accounts required |

---

## Quick Start

```bash
git clone https://github.com/JDDavenport/fleetwright.git
cd fleetwright
bash scripts/bootstrap.sh
```

Then open `http://localhost:3131` in your browser. Full instructions in [QUICKSTART.md](QUICKSTART.md).

---

## Installation

### Prerequisites

- Python 3.11+
- [Claude Code CLI](https://claude.ai/code) (Claude Max subscription — "bring your own")
- git
- Docker + Docker Compose (optional, for Postgres + cockpit container)

### One-command (recommended)

```bash
bash scripts/bootstrap.sh
```

### Docker path

```bash
cp .env.example .env          # set BRIDGE_SECRET
docker compose up -d          # Postgres + cockpit container
fleetwright-bridge            # bridge on the host (needs access to your claude CLI)
```

### Manual

```bash
pip install -e .
fleetwright-bridge &          # bridge at :8787
cd cockpit && npm install && npm run dev   # cockpit at :3131
```

---

## Key Concepts

### Domain agents

A domain agent is a persistent Claude Code session with a specific area of responsibility (e.g., `work`, `personal`, `research`). Each domain has a `CLAUDE.md` definition and its own working directory. Define yours in `config/domains.yaml`.

### Fleet runs

When a task needs isolated execution — code changes, long research, anything you don't want in a live session — the fleet engine spawns a Claude Code worker in a fresh git worktree inside a tmux session. Workers run headless with `--output-format stream-json` and are supervised by the reconciler.

### CEO orchestrator

The CEO is an always-on agent that holds your goals (in `WORKPLAN.md`), routes cross-domain tasks, and synthesizes fleet output. It starts automatically with the bridge.

### Bridge

The FastAPI server that ties everything together: it manages PTY sessions, exposes the REST + SSE API consumed by the cockpit, and wraps the fleet engine.

---

## Configuration

Key variables in `.env` (see `.env.example` for the full list):

| Variable | Default | Description |
|---|---|---|
| `BRIDGE_SECRET` | *(required)* | HMAC secret — `openssl rand -hex 32` |
| `DB_BACKEND` | `sqlite` | `sqlite` \| `postgres` \| `supabase` |
| `FLEET_MAX_PARALLEL` | `10` | Max concurrent fleet workers |
| `FLEETWRIGHT_ROOT` | `~/.fleetwright` | State, worktrees, and logs |
| `DEV_MODE` | `false` | Disable auth checks |

---

## Project structure

```
fleetwright/           Python package
  bridge/              FastAPI server + PTY manager
  fleet/               Worktree+tmux supervisor
  orchestrator/        CEO plan/fanout/harvest loop
  sdk/                 Shared modules (llm_call, ask_agent, …)
cockpit/               Next.js supervision UI
agents/                Agent definitions + registry
  examples/            CEO, work, personal example agents
config/                domains.yaml, model-registry.yaml
scripts/               bootstrap.sh, scan-secrets.py
tests/                 pytest suite (69 tests)
```

---

## Documentation

Full docs: [`docs/`](docs/) — or (once launched) **fleetwright.dev/docs**

- [Quick Start](QUICKSTART.md)
- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [Agent Authoring Guide](docs/agent-authoring.md)
- [Build Your Own Domain Agent](docs/domain-agent-tutorial.md)
- [Bridge API Reference](docs/api-reference.md)
- [Contributing](CONTRIBUTING.md)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). TL;DR: fork → branch → `pytest` → PR.

---

## License

Apache 2.0. See [LICENSE](LICENSE).
