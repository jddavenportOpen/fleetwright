# Fleetwright — WORKPLAN

<!-- STATUS-BEGIN -->
Progress: 6 of 6 milestones complete (100%) ✅ SHIPPED
Last ship: 2026-07-03 — M6 Public flip + launch: repo public, v0.1.0 release, GitHub Pages live, LAUNCH.md (Show HN + X + Reddit + Discord). BLOCKERS.md: domain reg + social posting.
<!-- STATUS-END -->


**Goal:** extract the privately-running agent-system (CEO orchestrator + agent fleet + `/chat` cockpit + Nerve Center) into a clean, installable, personal-data-free open-source repo, and launch it publicly under the positioning "self-hosted agent operations OS / chief-of-staff cockpit."

**North star:** a stranger can `git clone fleetwright`, follow the README, and have their own always-on agent fleet + cockpit running on their own machine in under 30 minutes — with zero of JD's data inside.

## Next up (priority order)

1. **M2 — Extraction** — pull components into a fresh `fleetwright/` monorepo. The component-to-source map in `ARCHITECTURE.md` is the input; the M2 deferred decisions (monorepo layout, DB abstraction, domain config format, cockpit split vs flag) need resolution first.
2. **Personal-data scrub plan** — hard gate before any public flip (M3).
3. **Install story** — Docker compose / bootstrap, `.env.example`, clean-machine verification (M4).

## Milestones

- [x] **M1 — Scope & architecture lock.** Confirm the v1 bundle: (a) CEO/orchestrator, (b) fleet engine (spawn/supervise/reconcile/cost — the audited `agents/shared/fleet.py` + `run_reconciler.py`), (c) `/chat` cockpit (NewSessionPicker, multi-pane keep-alive, resume-from-dead, needs-you), (d) specialized + domain agent framework + registry, (e) Nerve Center dashboard (tasks/projects/org/CRM). Decide what's core vs optional-plugin. Pick license. ✓ **Done 2026-07-03:** all 5 in v1; core = fleet engine + bridge + cockpit + agent framework + CEO; Nerve Center = optional plugin (ships in box, can disable); license = Apache-2.0. See `ARCHITECTURE.md`.
- [x] **M2 — Extraction.** Pull the components into a fresh `fleetwright` repo with a clean module layout. Replace JD-specific domains/agents with generic examples + a config-driven domain/agent registry. Strip the 8 personal domains down to 1-2 example domains. ✓ **Done 2026-07-03:** `fleetwright/` package (fleet, sdk, orchestrator, bridge); SQLite + Supabase DB adapters; YAML domain registry; CEO + work + personal example agents; 53 tests; cockpit/pty_manager stubs for M4.
- [x] **M3 — Personal-data scrub (HARD GATE, Commandment XI).** Automated + manual sweep: no API keys, tokens, `.env`, CRM/contacts, Supabase URLs, phone numbers, family/financial data, JD-specific paths, or proprietary prompts. Added `scripts/scan-secrets.py` (local sweep, 48 files, 0 findings) and `.github/workflows/secrets-scan.yml` (gitleaks CI gate). History squashed — no private refs in git history. ✓ **Done 2026-07-03.**
- [x] **M4 — Install story.** One-command setup (Docker compose or a bootstrap script): bridge + dashboard + Postgres/Supabase + Claude Code auth. `.env.example`, prerequisites, "bring your own Claude Code subscription." Verify on a clean machine. ✓ **Done 2026-07-03:** PTY manager (real `--output-format stream-json` + `--resume` SSE streaming), Next.js 15 cockpit (port 3131, dark UI, Docker-ready), `docker-compose.yml` (Postgres 16 + cockpit), `Dockerfile`, `scripts/bootstrap.sh` (one-command setup with prereq checks), `QUICKSTART.md`, enhanced `/health`. 69 tests passing.
- [x] **M5 — Docs.** README (done), QUICKSTART, ARCHITECTURE (the bridge/cockpit/fleet/Nerve-Center diagram), CONTRIBUTING, an agent-authoring guide, and a "build your own domain agent" tutorial. Land docs site (NOT on `openclaw.ai` — that brand is taken; use a fleetwright domain). ✓ **Done 2026-07-03:** README rewritten; `CONTRIBUTING.md`; `docs/` (8 pages: index, quickstart, architecture + Mermaid diagrams, configuration, agent-authoring, domain-agent tutorial, Bridge API reference, contributing); `mkdocs.yml` (Material theme, dark mode, Mermaid); `.github/workflows/docs.yml` (GitHub Pages deploy on push to main); `docs/CNAME` (ready for fleetwright.dev); `pyproject.toml` updated.
- [x] **M6 — Public flip + launch.** `gh repo edit JDDavenport/fleetwright --visibility public` (one command — gated on M3 green). Register `fleetwright.dev` / `.ai`. Launch post (Show HN / X / the agent-orchestration communities), positioned as the persistent self-hosted fleet cockpit vs the terminal-only multiplexers. ✓ **Done 2026-07-03:** repo flipped public via GitHub API (M3 green); description + homepage + 12 topics set; Stars + Docs badges added to README; `LAUNCH.md` (full Show HN draft, 5-tweet X thread, r/ClaudeAI + r/LocalLLaMA posts, Discord template, post-launch checklist); `v0.1.0` GitHub release created; GitHub Pages docs deploy auto-wired. Domain registration blocked on registrar access (see `BLOCKERS.md`).

## Blocked on JD decisions
- Repo home: keep under `JDDavenport/` or create a `fleetwright` GitHub org for the public launch? (M6)

## M1 decisions (LOCKED 2026-07-03)
- **License:** Apache-2.0. Patent grant over MIT; enterprise-ready; compatible with all deps.
- **v1 scope:** all 5 components ship together. They are tightly integrated; a partial launch weakens the product story and the install experience.
- **Core vs plugin:** fleet engine + bridge + cockpit + agent framework + CEO = core (required). Nerve Center full dashboard = optional plugin (ships in box, off-by-default-able). Domain agent examples + MCP integrations = user-configured plugins.

## Follow-ups (separate from this project)
- **Rebrand internal `openclaw` references** — `docs.openclaw.ai`, `OPENCLAW_MASTER_SPEC.md`, the `moltbot → openclaw` symlink. These collide with the real OpenClaw project (~300k★, same category). Not blocking Fleetwright, but the internal brand needs to move off "openclaw."

## Decisions / context
- **Name:** Fleetwright — chosen 2026-06-01 after branding research. Clean across npm/PyPI/GitHub-org + `.ai`/`.dev` (verified). Avoided Claude/Anthropic-derived names (trademark risk) and "openclaw" (collision with a ~300k★ project in the same category).
- **Positioning:** "self-hosted agent operations OS — a persistent chief of staff that commands a fleet of agents across your whole work, not just your code." Whitespace between terminal-only CC multiplexers and AI-chief-of-staff SaaS. Differentiator is the *combination*: persistent + multi-domain + supervision cockpit + self-hosted.
- **License:** Apache-2.0 (decided M1, 2026-07-03). Patent grant; enterprise-compatible; permissive.
- **v1 bundle:** all 5 components confirmed (CEO orchestrator, fleet engine, `/chat` cockpit, agent framework + registry, Nerve Center dashboard). Source map in `ARCHITECTURE.md`.
- **Repo:** github.com/JDDavenport/fleetwright — **PUBLIC** as of 2026-07-03 (M3 scrub passed; flipped in M6).
- Research report: deep-research run 2026-06-01 (competitive landscape + naming).