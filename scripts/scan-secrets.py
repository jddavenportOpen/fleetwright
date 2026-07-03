#!/usr/bin/env python3
"""
scripts/scan-secrets.py — Local secrets + personal-data scan for Fleetwright.

Runs before every commit (see .git/hooks/pre-commit) and in CI (via gitleaks).
This script catches JD-specific paths and patterns that gitleaks' default
ruleset doesn't cover (private repo names, personal paths, etc.).

Exit code:
  0 — clean
  1 — findings; prints offending file:line:match

Usage:
  python3 scripts/scan-secrets.py              # scan working tree
  python3 scripts/scan-secrets.py --staged     # scan git-staged files only
  python3 scripts/scan-secrets.py --all        # scan all git-tracked files
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# ── Root ──────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Pattern catalogue ─────────────────────────────────────────────────────────
# Each entry: (name, regex, allow_in_files)
# allow_in_files: set of filenames (basename) where the pattern is permitted.
PATTERNS: list[tuple[str, re.Pattern, set[str]]] = [
    # Real secrets
    ("anthropic-api-key",   re.compile(r"sk-ant-[A-Za-z0-9\-_]{40,}"),      set()),
    ("supabase-jwt",        re.compile(r"sbp_[A-Za-z0-9]{40,}"),             set()),
    ("github-token",        re.compile(r"ghp_[A-Za-z0-9]{36,}"),             set()),
    ("github-token-ghs",    re.compile(r"ghs_[A-Za-z0-9]{36,}"),             set()),
    ("telegram-bot-token",  re.compile(r"\d{8,12}:[A-Za-z0-9_\-]{35,}"),     set()),
    ("openai-key",          re.compile(r"sk-[A-Za-z0-9]{48}"),               set()),
    # Real Supabase project URLs (not placeholders)
    ("supabase-real-url",   re.compile(r"https://[a-z]{20,}\.supabase\.co"),  {".env.example"}),

    # Private paths / personal identifiers
    ("private-clawd-path",  re.compile(r"~/clawd/(?!projects/fleetwright)"),  set()),
    ("private-agent-system",re.compile(r"~/agent-system"),                    {"ARCHITECTURE.md"}),
    ("private-nerve-center",re.compile(r"nerve-center-v\d"),                  set()),
    ("private-jd-email",    re.compile(r"jddavenport46@gmail\.com|johndd@byu\.edu", re.I), set()),
    ("private-phone",       re.compile(r"\b7791\b"),                          set()),
    ("private-clawd-log",   re.compile(r"clawd-log\.sh"),                     {"WORKPLAN.md"}),
]

# Files to always skip (binary, vendored, generated)
SKIP_EXTENSIONS = {".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".gif", ".ico",
                   ".pdf", ".zip", ".tar", ".gz", ".whl", ".egg"}
SKIP_NAMES = {"gitleaks", "LICENSE", "WORKPLAN.md", "scan-secrets.py"}  # scanner exempts itself


def files_to_scan(mode: str) -> list[Path]:
    if mode == "staged":
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=REPO_ROOT, text=True
        )
    elif mode == "all":
        out = subprocess.check_output(
            ["git", "ls-files"],
            cwd=REPO_ROOT, text=True
        )
    else:  # working tree
        out = subprocess.check_output(
            ["git", "ls-files", "--others", "--cached", "--exclude-standard"],
            cwd=REPO_ROOT, text=True
        )
    paths = []
    for line in out.splitlines():
        p = REPO_ROOT / line.strip()
        if p.suffix in SKIP_EXTENSIONS or p.name in SKIP_NAMES:
            continue
        if p.is_file():
            paths.append(p)
    return paths


def scan(paths: list[Path]) -> list[tuple[str, int, str, str]]:
    """Return list of (rel_path, lineno, pattern_name, matched_text)."""
    findings = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(REPO_ROOT))
        for name, pattern, allowed_files in PATTERNS:
            if path.name in allowed_files:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                m = pattern.search(line)
                if m:
                    findings.append((rel, i, name, m.group(0)[:60]))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description="Local secrets + PII scan")
    mode_group = ap.add_mutually_exclusive_group()
    mode_group.add_argument("--staged", action="store_true", help="scan staged files only")
    mode_group.add_argument("--all", action="store_true", help="scan all tracked files")
    args = ap.parse_args()

    mode = "staged" if args.staged else ("all" if args.all else "working-tree")
    paths = files_to_scan(mode)

    findings = scan(paths)
    if not findings:
        print(f"scan-secrets: clean ({len(paths)} files scanned, mode={mode})")
        return 0

    print(f"scan-secrets: FINDINGS in {len(paths)} files (mode={mode})\n")
    for rel, lineno, name, match in findings:
        print(f"  {rel}:{lineno}  [{name}]  {match!r}")
    print(f"\n{len(findings)} finding(s). Fix before committing.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
