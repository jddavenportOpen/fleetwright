# Cockpit

The cockpit is the supervision UI for the Fleetwright fleet — a Next.js web app that shows live agent sessions, fleet status, and the Donna AI EA layer.

## Current Status: M4 (planned)

The cockpit extraction is planned for **milestone M4** (see `WORKPLAN.md`).

The cockpit extraction is planned for M4. M3 (personal-data scrub) is a hard gate before the cockpit UI is added to this repo.

## What ships in M2

The bridge API (`fleetwright/bridge/`) exposes REST + SSE endpoints that the future cockpit will consume. Session management (`/api/sessions`) returns stubs until M4.

## Running the bridge (M2)

```bash
pip install -e ".[dev]"
uvicorn fleetwright.bridge.main:app --reload
```

Browse to `http://localhost:8765/docs` for the interactive API docs.

## M4 Roadmap

- Extract `src/app/chat/` routes into this repo
- Wire sidebar links to the YAML-driven domain registry
- Remove any hardcoded config; support self-hosted
- Publish Docker image (`ghcr.io/fleetwright/cockpit`)
