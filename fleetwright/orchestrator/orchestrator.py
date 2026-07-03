"""
fleetwright/orchestrator/orchestrator.py — formal spawn/harvest/synthesize loop.

Implements the lead-agent abstraction. The orchestrator plans work, fans it out
to the fleet, harvests summaries, and synthesizes a final result.

Public API:
    Orchestrator(lead_model="flagship", workplan_path: Path, run_id: str)
        async plan(objective) -> Plan
        async fanout(plan)    -> list[SubagentTask]
        async harvest(tasks)  -> list[Summary]
        async synthesize(summaries) -> Result

Constraints (Anthropic multi-agent best practices — non-negotiable):
  * One level deep only — orchestrator REFUSES to spawn another orchestrator.
  * Subagents return SUMMARIES, not raw data.
  * Lead writes the plan to disk BEFORE spawning (context may truncate).
  * Structured task descriptors: {objective, format, tool_guidance, boundaries}.

Usage:
    orch = Orchestrator(lead_model="flagship", workplan_path=Path("WORKPLAN.md"), run_id="abc123")
    plan = await orch.plan("Research and summarize the top 5 open-source LLM frameworks")
    tasks = await orch.fanout(plan)
    summaries = await orch.harvest(tasks)
    result = await orch.synthesize(summaries)
"""
from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

logger = logging.getLogger(__name__)

# Optional dependency: fleet (if absent, use a stub spawner for tests)
try:
    from fleetwright.fleet.fleet import Fleet, RunHandle
except Exception:
    Fleet = None
    RunHandle = None

# Optional dependency: checkpoints
try:
    from fleetwright.fleet import checkpoints as _checkpoints
except Exception:
    _checkpoints = None

# Optional dependency: plan_file
try:
    from fleetwright.orchestrator.plan_file import PlanFile, Plan as PlanFileModel, PlanItem
except Exception:
    PlanFile = None


# ── Errors ─────────────────────────────────────────────────────────────────
class OrchestratorError(Exception):
    """Base class for orchestrator errors."""


class NestedOrchestratorError(OrchestratorError):
    """Raised when the orchestrator detects an attempt to spawn another orchestrator.

    Enforces Anthropic's "one level deep" invariant.
    """


class PlanValidationError(OrchestratorError):
    """Raised when a plan from the lead LLM fails schema validation."""


class PlanCancelledError(OrchestratorError):
    """Raised when the user cancels a pending plan."""


# ── Data ───────────────────────────────────────────────────────────────────
@dataclass
class SubagentTask:
    """A single task handed to a fleet worker."""
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    agent: str = "worker"
    objective: str = ""
    format: str = "summary"
    tool_guidance: str = ""
    boundaries: str = ""
    run_id: Optional[str] = None  # set after spawn


@dataclass
class Summary:
    """What a subagent returns — a summary, not raw data."""
    task_id: str
    run_id: Optional[str]
    text: str
    cost_usd: float = 0.0
    status: str = "done"


@dataclass
class OrchestratorResult:
    """Final synthesized result."""
    run_id: str
    objective: str
    synthesis: str
    task_summaries: list[Summary] = field(default_factory=list)
    total_cost_usd: float = 0.0


# ── Context var (detects nested orchestrator calls) ────────────────────────
_ORCHESTRATING = contextvars.ContextVar("_fw_orchestrating", default=False)


class Orchestrator:
    """Plan → fanout → harvest → synthesize loop.

    Typical usage:
        orch = Orchestrator(lead_model="flagship", workplan_path=path, run_id=run_id)
        plan = await orch.plan(objective)
        tasks = await orch.fanout(plan)
        summaries = await orch.harvest(tasks)
        result = await orch.synthesize(summaries)
    """

    def __init__(
        self,
        lead_model: str = "flagship",
        workplan_path: Optional[Path] = None,
        run_id: Optional[str] = None,
        max_workers: int = 6,
        llm_call: Optional[Callable] = None,
    ) -> None:
        self.lead_model = lead_model
        self.workplan_path = workplan_path or Path(f"WORKPLAN-{uuid.uuid4().hex[:8]}.md")
        self.run_id = run_id or str(uuid.uuid4())
        self.max_workers = max_workers
        self._llm_call = llm_call or _default_llm_call
        self._synthesizing = False

    async def plan(self, objective: str) -> list[SubagentTask]:
        """Call the lead model to decompose objective into subagent tasks."""
        if _ORCHESTRATING.get():
            raise NestedOrchestratorError(
                "orchestrator.plan() called inside an existing orchestration — "
                "Fleetwright enforces one level of nesting only"
            )

        prompt = _PLAN_PROMPT.format(objective=objective, max_workers=self.max_workers)
        raw = await self._llm_call(prompt, model=self.lead_model)

        tasks = _parse_plan(raw)
        if not tasks:
            raise PlanValidationError(f"lead model returned no tasks for objective: {objective!r}")

        # Validate: no task should name "orchestrator" as the agent (would imply 2nd level)
        for t in tasks:
            if "orchestrator" in t.agent.lower():
                raise NestedOrchestratorError(
                    f"task {t.task_id!r} names {t.agent!r} — orchestrator tasks are forbidden "
                    "(would create a nested hierarchy)"
                )

        # Write plan to disk BEFORE spawning (context may truncate mid-run)
        if PlanFile is not None:
            pf = PlanFile(self.workplan_path, self.run_id)
            plan_items = [
                PlanItem(item_id=t.task_id, text=t.objective, meta={"agent": t.agent})
                for t in tasks
            ]
            from fleetwright.orchestrator.plan_file import Plan as PF
            pf.write_initial(PF(run_id=self.run_id, items=plan_items))
        else:
            self.workplan_path.write_text(
                f"# WORKPLAN — {self.run_id}\n\n"
                + "\n".join(f"- [ ] [{t.task_id}] {t.objective}" for t in tasks)
                + "\n",
                encoding="utf-8",
            )

        logger.info("plan: %d tasks for %r", len(tasks), objective[:60])
        return tasks

    async def fanout(self, tasks: list[SubagentTask]) -> list[SubagentTask]:
        """Spawn each task as a fleet worker. Returns the same list with run_ids set."""
        token = _ORCHESTRATING.set(True)
        try:
            if Fleet is None:
                for t in tasks:
                    t.run_id = f"stub-{uuid.uuid4().hex[:8]}"
                    logger.info("stub spawn: %s — %s", t.task_id, t.objective[:60])
                return tasks

            fleet = Fleet(max_concurrency=self.max_workers)

            async def _spawn(t: SubagentTask) -> None:
                try:
                    handle = await asyncio.to_thread(
                        fleet.spawn, t.agent, t.objective, self.run_id
                    )
                    t.run_id = handle.run_id
                    logger.info("spawned %s → run %s", t.task_id, t.run_id)
                except Exception as e:
                    logger.error("spawn failed for %s: %s", t.task_id, e)
                    t.run_id = None

            await asyncio.gather(*[_spawn(t) for t in tasks])
            return tasks
        finally:
            _ORCHESTRATING.reset(token)

    async def harvest(self, tasks: list[SubagentTask]) -> list[Summary]:
        """Poll until all spawned runs are done; collect their outputs."""
        summaries: list[Summary] = []
        pending = [t for t in tasks if t.run_id]
        deadline = asyncio.get_event_loop().time() + 3600  # 1h max harvest window

        while pending and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(10)
            still_pending = []
            for t in pending:
                run_id = t.run_id
                if run_id and _checkpoints:
                    row = _checkpoints._fetch_row(run_id)
                    status = (row or {}).get("status", "running")
                else:
                    status = "done"  # stub: assume done immediately

                if status in ("done", "failed", "cancelled"):
                    from fleetwright.config import RUN_LOG_DIR
                    ev = RUN_LOG_DIR / f"{run_id}.events.jsonl"
                    text = ""
                    if ev.exists():
                        try:
                            text = _extract_summary(ev)
                        except Exception:
                            pass
                    cost = float((row or {}).get("cost_usd_total") or 0.0)
                    summaries.append(Summary(
                        task_id=t.task_id,
                        run_id=run_id,
                        text=text or f"(no output for {run_id})",
                        cost_usd=cost,
                        status=status,
                    ))
                else:
                    still_pending.append(t)
            pending = still_pending

        # Any tasks that timed out
        for t in pending:
            summaries.append(Summary(
                task_id=t.task_id,
                run_id=t.run_id,
                text=f"(timed out: {t.run_id})",
                status="timeout",
            ))

        logger.info("harvest: %d summaries collected", len(summaries))
        return summaries

    async def synthesize(self, summaries: list[Summary]) -> OrchestratorResult:
        """Call the lead model to synthesize subagent summaries into one result."""
        if self._synthesizing:
            raise NestedOrchestratorError("synthesize() called recursively on the same Orchestrator")
        self._synthesizing = True
        try:
            parts = "\n\n".join(
                f"**Task {s.task_id}** (status={s.status}):\n{s.text}"
                for s in summaries
            )
            prompt = _SYNTHESIZE_PROMPT.format(summaries=parts)
            synthesis = await self._llm_call(prompt, model=self.lead_model)
            total_cost = sum(s.cost_usd for s in summaries)
            return OrchestratorResult(
                run_id=self.run_id,
                objective="",  # caller sets if needed
                synthesis=synthesis,
                task_summaries=summaries,
                total_cost_usd=total_cost,
            )
        finally:
            self._synthesizing = False


# ── Prompts ────────────────────────────────────────────────────────────────
_PLAN_PROMPT = """\
You are a lead orchestrator agent. Your job is to decompose the following
objective into {max_workers} or fewer parallel sub-tasks, each of which can
be executed independently by a worker agent.

OBJECTIVE:
{objective}

Output a JSON array of task objects. Each task must have:
  - "task_id": short unique id (e.g. "t01")
  - "agent": agent label (e.g. "researcher", "writer", "analyst", "worker")
  - "objective": the full objective for this sub-task (self-contained)
  - "format": expected output format ("summary", "markdown", "json", "code")
  - "tool_guidance": which tools this worker should use
  - "boundaries": what this worker should NOT do

IMPORTANT: Never name "orchestrator" as the agent — that would create a
forbidden nested hierarchy. Workers must be leaf-level.

Respond with ONLY the JSON array, no other text.
"""

_SYNTHESIZE_PROMPT = """\
You are a lead orchestrator agent. Below are the summarized outputs from
your parallel worker agents. Synthesize them into a single coherent result.

WORKER SUMMARIES:
{summaries}

Write a clear, well-organized synthesis that integrates all the findings.
Focus on the most important insights and actionable conclusions.
"""


# ── LLM call stub (real impl uses fleetwright.sdk.claude_cli_client) ──────
async def _default_llm_call(prompt: str, model: str = "flagship") -> str:
    """Default LLM call — uses Claude CLI via subprocess."""
    try:
        from fleetwright.sdk.claude_cli_client import llm_call as _llm
        return await asyncio.to_thread(_llm, prompt, model=model)
    except ImportError:
        return f"[stub: no LLM client available; model={model}]"


# ── Plan parser ────────────────────────────────────────────────────────────
def _parse_plan(raw: str) -> list[SubagentTask]:
    """Parse JSON task array from lead model output."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON array in the text
        import re
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            logger.warning("could not parse plan JSON from: %s", text[:200])
            return []
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []

    if not isinstance(data, list):
        return []

    tasks = []
    for item in data:
        if not isinstance(item, dict):
            continue
        tasks.append(SubagentTask(
            task_id=str(item.get("task_id", uuid.uuid4().hex[:8])),
            agent=str(item.get("agent", "worker")),
            objective=str(item.get("objective", "")),
            format=str(item.get("format", "summary")),
            tool_guidance=str(item.get("tool_guidance", "")),
            boundaries=str(item.get("boundaries", "")),
        ))
    return tasks


def _extract_summary(events_jsonl: Path) -> str:
    """Extract the final text output from a stream-json events file."""
    texts = []
    try:
        for line in events_jsonl.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            if raw.get("type") == "assistant":
                for block in (raw.get("message") or {}).get("content") or []:
                    if block.get("type") == "text":
                        texts.append(block.get("text", ""))
    except Exception:
        pass
    return "\n".join(texts)[-4000:]  # last 4k chars
