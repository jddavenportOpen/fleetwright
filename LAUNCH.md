# Fleetwright Launch Playbook

Launch date: 2026-07-03  
Repo: https://github.com/JDDavenport/fleetwright  
Docs: https://fleetwright.dev (domain pending) / https://jddavenport.github.io/fleetwright/

---

## Positioning

**One-line:** Self-hosted agent operations OS — a persistent chief of staff that commands a fleet of AI agents across your whole work.

**The wedge:** Claude Code multiplexers (ccmux, tmux-cc, etc.) are terminal-only, session-per-task, no persistence. SaaS AI-chief-of-staff tools (Devin, etc.) are cloud-hosted, expensive, and lock you in. Fleetwright is the third option: persistent + multi-domain + supervision cockpit + self-hosted.

**Target reader:** solo developer / indie builder / researcher who runs Claude Code daily and wants to move from "individual coding sessions" to "always-on fleet that's working while I'm not."

---

## Show HN Submission

**Title (max 80 chars):**
> Show HN: Fleetwright – self-hosted fleet cockpit for Claude Code agents

**Text body (plain text for HN submission form):**

```
I built Fleetwright after realizing I was spending more time managing Claude Code
sessions than actually reviewing their output.

The problem: Claude Code is a great single-session tool, but running five parallel
sessions across different projects means lots of terminal tabs, manual re-attaching,
and no visibility into what's running where. The terminal multiplexers (ccmux, etc.)
help, but they're session managers — they don't hold state between runs, don't
supervise or route work, and have no cockpit.

What Fleetwright adds:

  • A persistent "CEO" agent that holds your goals and routes cross-domain work
  • A fleet engine that spawns Claude Code workers in isolated git worktrees (each
    gets its own branch, runs headless with --output-format stream-json, supervised
    by the reconciler)
  • A dark-mode Next.js supervision cockpit on port 3131 — sessions, fleet runs,
    domain status at a glance
  • Domain agents that re-attach on restart (they don't forget between sessions)
  • One-command setup: `bash scripts/bootstrap.sh` — SQLite by default, Postgres
    optional via Docker Compose

"Bring your own Claude Max subscription" — no metered API, no per-call costs.

Tech: FastAPI bridge (SSE streaming, HMAC auth), Next.js 15 cockpit, Python fleet
engine (tmux + worktree supervisor), SQLite/Postgres/Supabase adapters, 69 tests.

Apache-2.0. https://github.com/JDDavenport/fleetwright

Would love feedback on the architecture — particularly the PTY manager / bridge
design and the CEO orchestrator loop. Happy to answer questions.
```

**Where to post:** https://news.ycombinator.com/submit  
**Best time:** Tuesday/Wednesday 8-10am ET (peak HN engagement)

---

## X (Twitter) Thread

**Tweet 1 (hook):**
```
I got tired of juggling 5 Claude Code terminal tabs and building with duct tape.

So I built Fleetwright: self-hosted agent ops OS.

CEO orchestrator → domain agents → fleet of parallel workers → cockpit to watch it all.

One command to run. Apache-2.0. github.com/JDDavenport/fleetwright 🧵
```

**Tweet 2 (the problem):**
```
The problem with Claude Code at scale:

❌ Terminal tabs everywhere
❌ Sessions die between restarts
❌ No visibility into what's running
❌ Can't route work across domains (work / personal / research)

Multiplexers help, but they're session managers — not orchestrators.
```

**Tweet 3 (the solution):**
```
Fleetwright gives you:

✅ Persistent domain agents that re-attach on restart
✅ Fleet engine: N parallel workers, each in an isolated git worktree
✅ CEO orchestrator: always-on, holds your goals, routes cross-domain work
✅ Next.js supervision cockpit (dark mode, port 3131)
✅ BYOS: bring your own Claude Max subscription
```

**Tweet 4 (technical):**
```
Under the hood:

• FastAPI bridge — SSE streaming + HMAC auth
• PTY manager wraps `claude --output-format stream-json --resume`
• Fleet engine: tmux + git worktree supervisor, reconciler loop
• SQLite default / Postgres / Supabase adapters
• 69 tests

Full arch: github.com/JDDavenport/fleetwright/blob/main/docs/architecture.md
```

**Tweet 5 (CTA):**
```
One-command setup:

  git clone github.com/JDDavenport/fleetwright
  bash scripts/bootstrap.sh
  open http://localhost:3131

Docs: fleetwright.dev (in progress) / github.com/JDDavenport/fleetwright

Apache-2.0. Star if useful. Issues + PRs welcome.
```

---

## Reddit Posts

### r/ClaudeAI

**Title:** Show r/ClaudeAI: Fleetwright — open-source fleet cockpit for running persistent Claude Code agents

**Body:**
```
Hey Claude community,

I open-sourced a project I've been building: Fleetwright
https://github.com/JDDavenport/fleetwright

It's a self-hosted "agent operations OS" — you get:

**What it solves:** I was running multiple Claude Code sessions in parallel (work
projects, personal tasks, research) and there was no good way to supervise them,
route work between them, or have them persist state across restarts.

**Core components:**
- **CEO orchestrator** — always-on Claude Code session that holds your WORKPLAN
  and routes cross-domain work
- **Fleet engine** — spawns Claude Code workers in isolated git worktrees, runs
  headless, supervised by a reconciler loop
- **Bridge** — FastAPI server (SSE streaming, HMAC auth) connecting everything
- **Cockpit** — dark-mode Next.js dashboard on port 3131 for supervision

**Setup:**
```bash
git clone https://github.com/JDDavenport/fleetwright
bash scripts/bootstrap.sh
# opens cockpit at localhost:3131
```

Bring your own Claude Max subscription — no metered API costs.

Apache-2.0, 69 tests passing. Would love feedback from heavy Claude Code users
on the orchestration design.
```

### r/LocalLLaMA

**Title:** Fleetwright: self-hosted fleet cockpit for Claude Code — open-source, Apache-2.0

**Body:**
```
Not a local model, but I think this is relevant to this community's ethos of
owning your AI infrastructure.

Fleetwright: https://github.com/JDDavenport/fleetwright

It's an open-source agent operations OS that runs on your own machine. You
provide the Claude Code CLI (Max subscription, not metered API), and Fleetwright
gives you:

- Persistent domain agents that re-attach on restart
- Fleet engine that spawns N parallel workers in isolated git worktrees
- CEO orchestrator for cross-domain routing
- Supervision cockpit (Next.js, dark mode)

One-command setup: `bash scripts/bootstrap.sh`

The architecture is SQLite-first, Docker Compose optional, no cloud accounts
required. The bridge runs on FastAPI and streams via SSE.

Apache-2.0 / Python 3.11+ / Next.js 15.

Happy to discuss the architecture and trade-offs vs cloud-hosted alternatives.
```

---

## Discord Communities

Post in:
- **Claude Code Discord** (`#show-and-tell` or `#community-projects`)
- **Latent Space Discord** (`#projects`)
- **AI Engineer Discord** (`#show-and-tell`)

**Short template:**
```
Hey! Just open-sourced Fleetwright — self-hosted agent ops OS for Claude Code.

CEO orchestrator + domain agents + fleet engine (parallel workers in git 
worktrees) + Next.js supervision cockpit.

One command: `bash scripts/bootstrap.sh` → cockpit at localhost:3131

GitHub: https://github.com/JDDavenport/fleetwright  
Apache-2.0, 69 tests, bring your own Claude Max.

Would love feedback on the orchestration design!
```

---

## Domain Registration (BLOCKED — see BLOCKERS.md)

- `fleetwright.dev` — register via Google Domains / Squarespace / Porkbun
- `fleetwright.ai` — register via any ICANN registrar (typically $50-100/yr)
- Point both to GitHub Pages (CNAME already configured in `docs/CNAME`)
- Once registered, add CNAME records pointing to `jddavenport.github.io`

---

## Post-launch checklist

- [ ] Flip repo public (`gh repo edit JDDavenport/fleetwright --visibility public`) ✅ DONE 2026-07-03
- [ ] Set repo description + homepage (`fleetwright.dev`) ✅ DONE 2026-07-03
- [ ] Add GitHub topics ✅ DONE 2026-07-03
- [ ] Register `fleetwright.dev` + `fleetwright.ai` — BLOCKED (see BLOCKERS.md)
- [x] GitHub Pages live ✅ DONE 2026-07-03 — docs deployed to https://jddavenport.github.io/fleetwright/ (CNAME fleetwright.dev pending domain registration)
- [ ] Post Show HN — draft in this file, ready to submit
- [ ] Post X thread — draft in this file, ready to post
- [ ] Post r/ClaudeAI — draft in this file, ready to submit
- [ ] Post r/LocalLLaMA — draft in this file, ready to submit
- [ ] Post in agent Discord communities — draft in this file, ready to send
- [x] Create GitHub release v0.1.0 ✅ DONE 2026-07-03 — https://github.com/JDDavenport/fleetwright/releases/tag/v0.1.0
