# Build Your Own Domain Agent

This tutorial walks you through creating a custom domain agent from scratch. By the end you'll have a persistent `research` domain brain that can hold literature notes, track your reading list, and synthesize findings on demand.

The same steps apply to any domain — swap `research` for `finance`, `health`, `hobby`, or whatever makes sense for your life.

---

## What we're building

A **research domain agent** that:
- Maintains a reading list in `WORKPLAN.md`
- Summarizes papers and saves notes
- Answers questions about your research corpus
- Sends a weekly progress heartbeat

---

## Step 1: Create the working directory

Each domain agent has its own working directory where it stores state, notes, and output.

```bash
mkdir -p ~/fleetwright-domains/research
mkdir -p ~/fleetwright-domains/research/notes
mkdir -p ~/fleetwright-domains/research/state

# Create the initial WORKPLAN.md
cat > ~/fleetwright-domains/research/WORKPLAN.md << 'EOF'
# Research Domain — WORKPLAN

## Active reading list

<!-- Add papers/articles here -->

## In progress

<!-- Currently being read/summarized -->

## Notes index

<!-- Links to note files in ./notes/ -->

## Weekly report

Last updated: (none)
EOF
```

---

## Step 2: Write the agent definition

Create the `CLAUDE.md` file that defines the agent's identity:

```bash
mkdir -p agents/examples/research
```

Create `agents/examples/research/CLAUDE.md`:

```markdown
# Research Domain Agent — Fleetwright

You are the **research** agent for this Fleetwright installation. You are a
persistent brain for everything in the **research** domain: academic papers,
technical reading, literature reviews, and research notes.

## Responsibilities

- Maintain the reading list in `WORKPLAN.md`
- Summarize papers and save notes to `notes/<title>.md`
- Answer questions about the research corpus
- Surface connections between papers and active projects
- Coordinate with the work agent when research feeds a project

## State

Your state lives in `~/fleetwright-domains/research/`:
- `WORKPLAN.md` — reading list, in-progress items, notes index
- `notes/` — one Markdown file per paper/article
- `state/report.md` — weekly status summary (updated by heartbeat)

## Adding a new paper

When asked to add a paper:
1. Add it to the reading list in `WORKPLAN.md`
2. Create a stub `notes/<title>.md` with title, authors, URL, and a 2-line summary of why it's relevant

## Summarizing a paper

When asked to summarize a paper (given a URL or PDF path):
1. Read the paper
2. Write a structured note to `notes/<title>.md`:
   - Title, authors, year
   - 3-sentence abstract
   - Key contributions (bulleted)
   - Connections to current work
   - "Worth reading in full?" (yes/no + one-line reason)

## Communication style

- Academic but concise
- Lead with the most useful finding, not the setup
- When surfacing connections, be specific: cite the note file and the relevant section

## What you don't do

- You don't manage work tasks — route those to the work agent
- You don't make purchases or manage subscriptions
- You don't push changes to code repositories

## Heartbeat

When run as a heartbeat:
1. Review `WORKPLAN.md` for overdue reading items
2. Count notes written this week
3. Write a concise update to `state/report.md` (under 150 words)
4. Flag anything that's been "in progress" for more than 7 days
```

---

## Step 3: Register the agent

Add your agent to `agents/registry.json`:

```json
{
  "name": "research",
  "kind": "domain",
  "description": "Research domain agent — papers, literature review, and research notes.",
  "model": "review",
  "definition": "agents/examples/research/CLAUDE.md",
  "scope": "domain"
}
```

Open `agents/registry.json` and add this entry to the `agents` array:

```bash
# Before editing, verify the current registry
cat agents/registry.json
```

The `"model": "review"` tier is appropriate for reading and summarizing — it's more capable than `"agent"` (good for analysis) but cheaper than `"flagship"`.

---

## Step 4: Add the domain to `domains.yaml`

If `config/domains.yaml` doesn't exist yet, copy the example:

```bash
cp config/domains.example.yaml config/domains.yaml
```

Add the research domain:

```yaml
domains:
  - name: work
    description: "Primary work domain"
    cwd: "~/fleetwright-domains/work"
    agent_definition: "agents/examples/work/CLAUDE.md"
    model: agent
    mcp_servers: []
    auto_resume: true

  - name: personal
    description: "Personal domain"
    cwd: "~/fleetwright-domains/personal"
    agent_definition: "agents/examples/personal/CLAUDE.md"
    model: agent
    mcp_servers: []
    auto_resume: true

  # ← ADD THIS:
  - name: research
    description: "Research papers, literature review, and technical reading"
    cwd: "~/fleetwright-domains/research"
    agent_definition: "agents/examples/research/CLAUDE.md"
    model: review
    mcp_servers: []
    auto_resume: false   # start manually until you're sure it's useful
```

`auto_resume: false` means the domain won't start automatically on bridge boot. You can change it to `true` once you've verified the agent works as expected.

---

## Step 5: Restart the bridge

The bridge loads `domains.yaml` at startup. Restart it to pick up the new domain:

```bash
# If running via bootstrap.sh
kill $(cat ~/.fleetwright/bridge.pid) && fleetwright-bridge &

# Or just Ctrl-C and restart
fleetwright-bridge
```

Verify the new domain appears:

```bash
curl http://localhost:8787/api/domains | python3 -m json.tool
# → should show { "domains": [..., {"name": "research", "active": false}] }
```

---

## Step 6: Start the domain and test it

### Via the cockpit

Open `http://localhost:3131`, find the **research** domain in the Domains panel, and click to activate it.

### Via the CLI

```bash
python3 -m fleetwright.sdk.ask_agent research "What's your current reading list?"
```

If this is a fresh domain, the agent will see an empty `WORKPLAN.md` and tell you so. Add a paper:

```bash
python3 -m fleetwright.sdk.ask_agent research \
  "Add this paper to the reading list: 'Attention Is All You Need' by Vaswani et al. (2017). It's foundational for understanding transformer architectures."
```

Then verify:

```bash
cat ~/fleetwright-domains/research/WORKPLAN.md
```

You should see the paper added to the reading list.

---

## Step 7: Wire up inter-agent messaging (optional)

Your research agent can receive questions from other agents. For example, the CEO can route research queries automatically:

In `agents/examples/ceo/CLAUDE.md`, add a routing rule:

```markdown
## Routing rules

- Research questions, paper summaries, literature review → route to `research`
  via `ask_agent research "..."`
```

Test it:

```bash
python3 -m fleetwright.sdk.ask_agent ceo \
  "Find recent papers on multi-agent systems and add the best ones to the reading list."
```

The CEO should route this to the research agent automatically.

---

## Step 8: Schedule a heartbeat (optional)

Add a cron job to get a weekly research summary:

```bash
# Open crontab
crontab -e

# Add this line (runs every Monday at 08:30)
30 8 * * 1 python3 -m fleetwright.sdk.ask_agent research "Run your weekly heartbeat." --caller scheduler
```

The heartbeat will update `state/report.md`. You can surface it in the cockpit or pipe it to Telegram via `notify.py`.

---

## Troubleshooting

**Domain doesn't appear in `/api/domains`**
Check that `config/domains.yaml` is valid YAML and the bridge was restarted after editing.

**Agent can't find its working directory**
Verify the `cwd` path in `domains.yaml` exists: `ls ~/fleetwright-domains/research`.

**`ask_agent` returns "target not found or not active"**
The domain isn't running. Either set `auto_resume: true` in `domains.yaml` and restart the bridge, or start it manually via the cockpit.

**Agent ignores part of the definition**
Very long `CLAUDE.md` files can dilute focus. Keep each domain's definition under ~400 words. Move rarely-used instructions to a `notes/INSTRUCTIONS.md` that the agent reads on demand.

---

## What's next

- [Agent Authoring Guide](agent-authoring.md) — SDK reference and design patterns
- [Configuration](configuration.md) — model tiers, MCP servers, and more
- [Architecture](architecture.md) — how the bridge manages domain sessions
