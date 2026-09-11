# Fleetwright — Quick Start

## Prerequisites

- Python 3.11+ (recommend 3.12+)
- Claude Code subscription ("bring your own") — https://claude.ai/code
- git
- Docker + Docker Compose (recommended, for Postgres + cockpit UI)

---

## 1. Clone and configure

```bash
git clone https://github.com/jddavenportOpen/fleetwright.git
cd fleetwright
cp .env.example .env
# Edit .env: set BRIDGE_SECRET to a random string
openssl rand -hex 32   # paste this value into BRIDGE_SECRET in .env
```

---

## 2. One-command install

```bash
bash scripts/bootstrap.sh
```

This:
- Checks Python >= 3.11, git, and claude CLI
- Copies `.env.example` → `.env` (won't overwrite an existing `.env`)
- Generates a random `BRIDGE_SECRET` if still at placeholder value
- Runs `pip install -e .`
- Creates `~/.fleetwright/` directory structure
- Starts Docker services (db + cockpit) if Docker is available
- Starts the bridge in the background on port 8787

---

## 3. Docker path (recommended)

```bash
# Start Postgres + cockpit
docker compose up -d

# Start the bridge on the host (needs access to your claude CLI)
fleetwright-bridge
```

The cockpit connects to the bridge via `http://host.docker.internal:8787` inside Docker.

---

## 4. Manual path (no Docker)

```bash
pip install -e .

# Bridge (port 8787)
fleetwright-bridge

# Cockpit (port 3131) — in a separate terminal
cd cockpit
npm install
npm run dev
```

No Postgres needed — Fleetwright defaults to SQLite at `~/.fleetwright/state/fleetwright.db`.

---

## 5. Verify

```bash
# Bridge health check
curl http://localhost:8787/health
# → {"status":"ok","version":"0.2.0","claude_binary":"/opt/homebrew/bin/claude",...}

# Open cockpit dashboard
open http://localhost:3131
```

---

## Configuration

Key variables in `.env`:

| Variable | Default | Description |
|---|---|---|
| `BRIDGE_SECRET` | *(required)* | HMAC secret shared between bridge and cockpit. Generate with `openssl rand -hex 32`. |
| `HOST` | `127.0.0.1` | Bridge bind address. |
| `PORT` | `8787` | Bridge port. |
| `COCKPIT_PORT` | `3131` | Cockpit port (Docker only). |
| `BRIDGE_URL` | `http://host.docker.internal:8787` | Bridge URL as seen by the cockpit container. |
| `NEXT_PUBLIC_BRIDGE_URL` | `http://localhost:8787` | Bridge URL as seen by browser clients. |
| `DB_BACKEND` | `sqlite` | Storage backend: `sqlite` \| `postgres` \| `supabase`. |
| `DATABASE_URL` | — | Postgres connection string (when `DB_BACKEND=postgres`). |
| `POSTGRES_PASSWORD` | `fleetwright_dev` | Postgres password (Docker only). |
| `FLEET_MAX_PARALLEL` | `10` | Max parallel fleet runs (no hard ceiling — hardware is the real limit). |
| `FLEET_BASE_BRANCH` | `main` | Base git branch for worktree spawning. |
| `FLEETWRIGHT_ROOT` | `~/.fleetwright` | Root directory for state, worktrees, and logs. |
| `DEV_MODE` | `false` | Disable auth checks (development only). |

---

## Bring your own Claude Code subscription

Fleetwright uses **your** Claude Code subscription — not the metered API. It:

- Discovers the `claude` CLI automatically (checks `/opt/homebrew/bin/claude`, `~/.claude/local/claude`, then `PATH`)
- Strips `ANTHROPIC_API_KEY` from worker environments so workers authenticate via Max subscription (not metered billing)
- Requires you to be signed in: run `claude` once interactively to authenticate before starting workers

If `claude` is not in any of the standard locations, set `BRIDGE_ALLOWED_CWD_PREFIXES` and ensure `claude` is on your `PATH` before starting the bridge.

---

## Stopping

```bash
# Stop Docker services
docker compose down

# Stop the bridge (if started by bootstrap.sh)
kill $(cat ~/.fleetwright/bridge.pid)

# Or just Ctrl-C if running in foreground
```

---

## Troubleshooting

**Bridge won't start / port already in use**
```bash
lsof -i :8787   # find what's using the port
kill <PID>
fleetwright-bridge
```

**`claude` not found**
The bridge falls back to `"claude"` on `PATH`. If workers fail to spawn, install Claude Code from https://claude.ai/code and run `claude` once to authenticate.

**Cockpit can't reach bridge** (Docker)
The cockpit uses `http://host.docker.internal:8787` to reach the host bridge. On Linux, `host.docker.internal` requires Docker 20.10+. If it fails, set `BRIDGE_URL` to your host's LAN IP in `.env`.

**Workers fail with auth errors**
Fleetwright strips `ANTHROPIC_API_KEY` from worker environments to force Max subscription auth. If you're seeing 401s, run `claude` interactively to refresh your session token.

**SQLite vs Postgres**
The default `sqlite` backend is fine for a single machine. Switch to `postgres` (via Docker or an external host) when running multiple bridge instances or when you need persistent fleet history across restarts.
