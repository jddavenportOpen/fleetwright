# Fleetwright — CHANGELOG

Append-only record of what's shipped. Newest at top.

---

## 2026-07-03 — v0.1.0 public launch

- 15:27 — **M6 shipped:** repo public (JDDavenport/fleetwright, visibility=public), v0.1.0 release, GitHub Pages live (jddavenport.github.io/fleetwright), LAUNCH.md ready (Show HN + X + Reddit + Discord). Domain reg + social posting in BLOCKERS.md.
- **M6 complete:** public flip + launch. Repo flipped public (`JDDavenport/fleetwright` → visibility: public). GitHub repo description, homepage (`fleetwright.dev`), and topics set via API. README: added GitHub Stars badge + Docs badge. `LAUNCH.md`: complete launch playbook — Show HN submission (ready to post), X/Twitter thread (5 tweets), r/ClaudeAI + r/LocalLLaMA posts, Discord template, post-launch checklist. GitHub Pages docs deploy wired (docs.yml auto-deploys on push). `v0.1.0` release created. WORKPLAN: 6/6 milestones complete.
- Domain registration (`fleetwright.dev` + `fleetwright.ai`) logged as external blocker in `BLOCKERS.md` — requires JD's registrar account + payment.
- M5 complete: docs. README rewritten (was gitleaks README); CONTRIBUTING.md; 7-page MkDocs Material docs site (docs/: index, quickstart, architecture + Mermaid diagrams, configuration, agent-authoring guide, domain-agent tutorial, Bridge API reference, contributing); mkdocs.yml (Material theme, dark mode, Mermaid superfences, search, code copy, fleetwright.dev site URL); .github/workflows/docs.yml (GitHub Pages deploy on push to main); docs/CNAME (ready for fleetwright.dev — domain registration in M6); ARCHITECTURE.md data flow upgraded to Mermaid diagram + interface table; pyproject.toml: mkdocs-material added to dev deps, docs URL updated to fleetwright.dev. WORKPLAN progress: 5/6.
- M4 complete: install story. PTY manager (send_turn SSE streaming via --output-format stream-json + --resume), Next.js 15 cockpit (port 3131, dark UI, Docker multi-stage build), docker-compose.yml (Postgres 16 + cockpit), Dockerfile, scripts/bootstrap.sh (one-command setup: prereq checks, .env copy, BRIDGE_SECRET gen, pip install, dirs, docker up, bridge start), QUICKSTART.md, enhanced /health endpoint. 69 tests passing (53 original + 16 new PTY manager tests).
- 14:42 — M3 personal-data scrub: scan-secrets.py (50 files, 0 findings) + gitleaks CI gate + history squashed clean
- M3 complete: personal-data scrub (hard gate). Automated + manual sweep — no API keys, tokens, private paths, contact data, or proprietary prompts. Added `.gitleaks.toml` and GitHub Actions secrets-scan CI gate (`secrets-scan.yml`). All private source-repo references removed from public-facing docs.
- M2 complete: `fleetwright` Python package — fleet engine (worktree+tmux supervisor), SDK (circuit breaker, model registry, ask_agent, claude_cli_client), orchestrator (plan/fanout/harvest/synthesize), FastAPI bridge (fleet/session/agent/domain routes). SQLite default adapter; Supabase HTTP adapter. YAML domain registry; CEO + work + personal example agents. 53 tests pass. Stubs for pty_manager + cockpit (M4).
- M1 complete: Apache-2.0 license locked; all 5 components confirmed for v1 (fleet engine + bridge + cockpit + agent framework + CEO = core; Nerve Center = optional plugin); architecture documented in ARCHITECTURE.md.
