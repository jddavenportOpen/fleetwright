"""fleetwright/sdk/claude_cli_client.py — thin Claude CLI wrapper for LLM completions.

Calls `claude -p <prompt>` via subprocess and returns the text output.
Intended for use by the orchestrator's _default_llm_call and any agent that
needs a quick one-shot completion without spinning up a full fleet worker.

Usage:
    from fleetwright.sdk.claude_cli_client import llm_call
    result = llm_call("Summarize the following...", model="agent")

Environment:
    CLAUDE_BIN   — override the path to the claude binary (default: "claude")
    LLM_TIMEOUT  — per-call timeout in seconds (default: 120)
"""
from __future__ import annotations

import logging
import os
import shlex
import subprocess
from typing import Optional

from fleetwright.sdk.model_registry import cli_id as _model_id

logger = logging.getLogger(__name__)

_CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
_DEFAULT_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "120"))


class LLMCallError(Exception):
    """Raised when the Claude CLI call fails."""


def llm_call(
    prompt: str,
    *,
    model: str = "agent",
    timeout: int = _DEFAULT_TIMEOUT,
    extra_args: Optional[list[str]] = None,
) -> str:
    """Run `claude -p <prompt>` and return the text output.

    Args:
        prompt: The prompt text to send.
        model: Tier name ("flagship", "review", "agent", "bulk") or raw model ID.
        timeout: Seconds before the call is killed (default 120).
        extra_args: Additional CLI flags to pass through.

    Returns:
        The assistant's text response.

    Raises:
        LLMCallError: If the CLI call fails, times out, or returns non-zero.
    """
    try:
        model_id = _model_id(model)
    except Exception:
        model_id = model

    argv = [_CLAUDE_BIN, "-p", prompt, "--model", model_id]
    if extra_args:
        argv.extend(extra_args)

    logger.debug("llm_call: %s %s ...", _CLAUDE_BIN, model_id)
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise LLMCallError(
            f"claude binary not found at {_CLAUDE_BIN!r}; "
            "ensure Claude Code CLI is installed and in PATH"
        )
    except subprocess.TimeoutExpired as exc:
        raise LLMCallError(
            f"llm_call timed out after {timeout}s (model={model_id})"
        ) from exc

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()[:500]
        raise LLMCallError(
            f"claude exited {result.returncode} (model={model_id}): {stderr or '(no stderr)'}"
        )

    return result.stdout.strip()
