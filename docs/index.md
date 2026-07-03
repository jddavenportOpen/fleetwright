# Fleetwright

**Self-hosted agent operations OS — a persistent chief of staff that commands a fleet of AI agents across your whole work.**

Fleetwright gives you a **persistent, always-on agent fleet** on your own machine:

- A **CEO orchestrator** holds your goals and routes work to the right agent or fleet worker.
- **Domain agents** are always-on Claude Code sessions scoped to an area of your work (e.g., `work`, `personal`, `research`).
- The **fleet engine** spawns N Claude Code workers in parallel, each in an isolated git worktree.
- The **cockpit** is a dark-mode Next.js dashboard for supervising all of it.

## Get started

- [Quick Start](quickstart.md) — running in under 5 minutes
- [Architecture](architecture.md) — how the pieces fit together
- [Configuration](configuration.md) — full environment variable reference

## Build your own agents

- [Agent Authoring Guide](agent-authoring.md) — write agent definitions with the Fleetwright SDK
- [Domain Agent Tutorial](domain-agent-tutorial.md) — step-by-step: build a custom domain brain

## Reference

- [Bridge API Reference](api-reference.md) — REST + SSE endpoints
- [Contributing](contributing.md) — development setup and PR process

---

Fleetwright is **open source** under the Apache 2.0 license.  
Source: [github.com/JDDavenport/fleetwright](https://github.com/JDDavenport/fleetwright)
