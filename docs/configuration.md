# Configuration

All configuration is via environment variables loaded from `.env`. Copy `.env.example` to `.env` and fill in your values.

```bash
cp .env.example .env
openssl rand -hex 32   # generate BRIDGE_SECRET
```

---

## Core

| Variable | Default | Required | Description |
|---|---|---|---|
| `FLEETWRIGHT_ROOT` | `~/.fleetwright` | No | Root directory for all state, worktrees, and logs |

---

## Bridge

| Variable | Default | Required | Description |
|---|---|---|---|
| `BRIDGE_SECRET` | — | **Yes** | HMAC secret shared between bridge and cockpit. Generate with `openssl rand -hex 32`. |
| `HOST` | `127.0.0.1` | No | Bridge bind address. Use `0.0.0.0` to expose on LAN. |
| `PORT` | `8787` | No | Bridge listen port. |
| `DEV_MODE` | `false` | No | Set `true` to disable auth checks. Development only. |
| `SESSION_IDLE_TIMEOUT_SEC` | `3600` | No | Seconds before an idle PTY session is reaped. |
| `CORS_ORIGINS` | `*` | No | Comma-separated allowed CORS origins. Narrow in production. |

---

## Database

| Variable | Default | Required | Description |
|---|---|---|---|
| `DB_BACKEND` | `sqlite` | No | Storage backend: `sqlite` \| `postgres` \| `supabase` |
| `SQLITE_PATH` | `~/.fleetwright/state/fleetwright.db` | No | SQLite file path (when `DB_BACKEND=sqlite`) |
| `DATABASE_URL` | — | When using postgres | PostgreSQL connection string, e.g. `postgresql://user:pass@localhost:5432/fleetwright` |
| `SUPABASE_URL` | — | When using supabase | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | — | When using supabase | Supabase service role key (not the anon key) |

### Choosing a backend

| Backend | When to use |
|---|---|
| `sqlite` (default) | Single machine, development, or when you don't need cross-restart fleet history |
| `postgres` | Multiple bridge instances, persistent fleet history, production workloads |
| `supabase` | If you're already using Supabase for other parts of your stack |

---

## Fleet engine

| Variable | Default | Description |
|---|---|---|
| `FLEET_MAX_PARALLEL` | `10` | Maximum number of concurrent fleet runs. Set by hardware limits — there is no hard cap in the code. |
| `FLEET_BASE_BRANCH` | `main` | Git branch used as the base for new worktrees (`git worktree add -b task/{run_id} {base}`). |
| `FLEET_WORKTREE_ROOT` | `~/.fleetwright/.fleet-worktrees` | Directory where fleet worktrees are created. |
| `FLEET_RUN_LOG_DIR` | `~/.fleetwright/logs/runs` | Directory for `*.events.jsonl` and `*.events.err` files. |
| `FLEET_GIT_ROOT` | `cwd at startup` | Git repo root used for worktree operations. |

---

## Model registry

| Variable | Default | Description |
|---|---|---|
| `MODEL_REGISTRY_PATH` | `config/model-registry.yaml` | Path to the model registry YAML. |
| `MODEL_TIER_OVERRIDE_FLAGSHIP` | — | Override the `flagship` tier model ID (e.g., `claude-fable-5`). |
| `MODEL_TIER_OVERRIDE_AGENT` | — | Override the `agent` tier model ID (e.g., `claude-sonnet-4-6`). |
| `MODEL_TIER_OVERRIDE_REVIEW` | — | Override the `review` tier. |
| `MODEL_TIER_OVERRIDE_BULK` | — | Override the `bulk` tier. |

The model registry (`config/model-registry.yaml`) maps tier names to model IDs. Agents reference tiers (e.g., `"flagship"`) rather than hardcoded model IDs so you can update all agents by editing one file.

---

## Domain registry

| Variable | Default | Description |
|---|---|---|
| `FLEETWRIGHT_DOMAINS_FILE` | `config/domains.yaml` | Path to your domain registry YAML. |

`config/domains.yaml` defines which domain agents exist, where their working directories are, and which MCP servers they should connect to. See `config/domains.example.yaml` for the format.

---

## Cockpit

| Variable | Default | Description |
|---|---|---|
| `COCKPIT_PORT` | `3131` | Cockpit container port (Docker only). |
| `BRIDGE_URL` | `http://host.docker.internal:8787` | Bridge URL as seen by the cockpit **server** (server-side fetch inside Docker). |
| `NEXT_PUBLIC_BRIDGE_URL` | `http://localhost:8787` | Bridge URL as seen by **browser** clients. Must be publicly reachable. |

---

## Notifications (optional)

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token for agent alerts via `sdk/notify.py`. |
| `TELEGRAM_CHAT_ID` | — | Telegram chat ID to send alerts to. |

---

## Claude CLI

| Variable | Default | Description |
|---|---|---|
| `CLAUDE_BIN` | auto-detected | Path to the `claude` binary. Auto-detected from `/opt/homebrew/bin/claude`, `~/.claude/local/claude`, then `PATH`. |
| `LLM_TIMEOUT` | `120` | Timeout in seconds for `llm_call()` (one-shot Claude CLI completions). |
| `ASK_AGENT_TIMEOUT_SEC` | `120` | Timeout for `ask_agent()` bridge calls. |

---

## Docker

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_PASSWORD` | `fleetwright_dev` | Postgres password used by `docker-compose.yml`. |
| `DB_PORT` | `5432` | Postgres external port (Docker Compose). |
