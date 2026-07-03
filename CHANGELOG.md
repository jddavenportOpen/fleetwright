# Fleetwright — CHANGELOG

Append-only record of what's shipped. Newest at top.

---

## 2026-07-03

- M4 complete: install story. PTY manager (send_turn SSE streaming via --output-format stream-json + --resume), Next.js 15 cockpit (port 3131, dark UI, Docker multi-stage build), docker-compose.yml (Postgres 16 + cockpit), Dockerfile, scripts/bootstrap.sh (one-command setup: prereq checks, .env copy, BRIDGE_SECRET gen, pip install, dirs, docker up, bridge start), QUICKSTART.md, enhanced /health endpoint. 69 tests passing (53 original + 16 new PTY manager tests).
- 14:42 — M3 personal-data scrub: scan-secrets.py (50 files, 0 findings) + gitleaks CI gate + history squashed clean
- M3 complete: personal-data scrub (hard gate). Automated + manual sweep — no API keys, tokens, private paths, contact data, or proprietary prompts. Added `.gitleaks.toml` and GitHub Actions secrets-scan CI gate (`secrets-scan.yml`). All private source-repo references removed from public-facing docs.
- M2 complete: `fleetwright` Python package — fleet engine (worktree+tmux supervisor), SDK (circuit breaker, model registry, ask_agent, claude_cli_client), orchestrator (plan/fanout/harvest/synthesize), FastAPI bridge (fleet/session/agent/domain routes). SQLite default adapter; Supabase HTTP adapter. YAML domain registry; CEO + work + personal example agents. 53 tests pass. Stubs for pty_manager + cockpit (M4).
- M1 complete: Apache-2.0 license locked; all 5 components confirmed for v1 (fleet engine + bridge + cockpit + agent framework + CEO = core; Nerve Center = optional plugin); architecture documented in ARCHITECTURE.md.
