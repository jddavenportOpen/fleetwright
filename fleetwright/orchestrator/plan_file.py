"""
fleetwright/orchestrator/plan_file.py — Manus todo.md pattern for fleet agents.

An agent re-reads a checklist file each loop and edits it in-place. Format:
plain markdown (- [ ] / - [x]) with optional trailing HTML-comment metadata.

Public API:
    class PlanFile:
        def __init__(self, path: Path, run_id: str)
        def write_initial(self, plan: Plan) -> None
        def read(self) -> list[PlanItem]
        def mark_done(self, item_id: str) -> None
        def add_item(self, item: PlanItem) -> None
        def edit(self, item_id: str, new_text: str) -> None

Concurrency: every mutation holds an fcntl advisory lock on a sidecar lockfile,
then writes via tmpfile + os.replace (POSIX-atomic).
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False


@dataclass
class PlanItem:
    item_id: str
    text: str
    done: bool = False
    meta: dict = field(default_factory=dict)


@dataclass
class Plan:
    run_id: str
    items: list[PlanItem] = field(default_factory=list)
    title: Optional[str] = None


_CHECK_RE = re.compile(r"^\s*[-*]\s*\[(?P<mark>[ xX])\]\s*(?P<text>.*?)\s*$")
_META_RE = re.compile(r"^<!--\s*meta:\s*(?P<json>\{.*?\})\s*-->$")


class PlanFile:
    """Atomic, lock-safe WORKPLAN.md reader/writer."""

    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self._lock_path = path.with_suffix(".lock")
        self._counter = 0

    @contextmanager
    def _locked(self) -> Iterator[None]:
        if _HAS_FCNTL:
            with open(self._lock_path, "w") as lf:
                fcntl.flock(lf, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lf, fcntl.LOCK_UN)
        else:
            yield

    def _next_id(self) -> str:
        self._counter += 1
        return f"i{self._counter:02d}"

    def write_initial(self, plan: Plan) -> None:
        title = plan.title or f"WORKPLAN — run {plan.run_id}"
        lines = [f"# {title}\n\n"]
        for item in plan.items:
            mark = "x" if item.done else " "
            lines.append(f"- [{mark}] {item.text}\n")
            meta_str = json.dumps(item.meta) if item.meta else json.dumps({"item_id": item.item_id})
            lines.append(f"<!-- meta: {meta_str} -->\n")
        with self._locked():
            self._atomic_write("".join(lines))

    def read(self) -> list[PlanItem]:
        if not self.path.exists():
            return []
        text = self.path.read_text(encoding="utf-8", errors="replace")
        return self._parse(text)

    def _parse(self, text: str) -> list[PlanItem]:
        lines = text.splitlines()
        items: list[PlanItem] = []
        i = 0
        while i < len(lines):
            m = _CHECK_RE.match(lines[i])
            if m:
                done = m.group("mark").lower() == "x"
                item_text = m.group("text")
                meta = {}
                # peek at next line for meta comment
                if i + 1 < len(lines):
                    mm = _META_RE.match(lines[i + 1].strip())
                    if mm:
                        try:
                            meta = json.loads(mm.group("json"))
                            i += 1  # consume meta line
                        except json.JSONDecodeError:
                            pass
                item_id = meta.pop("item_id", None) or self._next_id()
                items.append(PlanItem(item_id=item_id, text=item_text, done=done, meta=meta))
            i += 1
        return items

    def mark_done(self, item_id: str) -> None:
        with self._locked():
            self._mutate(lambda items: [
                PlanItem(i.item_id, i.text, True, i.meta) if i.item_id == item_id else i
                for i in items
            ])

    def add_item(self, item: PlanItem) -> None:
        with self._locked():
            self._mutate(lambda items: items + [item])

    def edit(self, item_id: str, new_text: str) -> None:
        with self._locked():
            self._mutate(lambda items: [
                PlanItem(i.item_id, new_text, i.done, i.meta) if i.item_id == item_id else i
                for i in items
            ])

    def _mutate(self, fn) -> None:
        items = self.read()
        new_items = fn(items)
        plan = Plan(run_id=self.run_id, items=new_items)
        # Preserve title from existing file
        if self.path.exists():
            first = self.path.read_text(encoding="utf-8").splitlines()[:1]
            if first and first[0].startswith("# "):
                plan.title = first[0][2:].strip()
        self.write_initial(plan)

    def _atomic_write(self, content: str) -> None:
        dir_ = self.path.parent
        dir_.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dir_, prefix=".planfile-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
