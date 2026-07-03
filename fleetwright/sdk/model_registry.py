"""
fleetwright/sdk/model_registry.py — read-once cached loader for config/model-registry.yaml.

Every model-selection seam resolves tiers through here instead of hardcoding
versioned claude-* ids. To upgrade a model: edit config/model-registry.yaml.

Usage:
    from fleetwright.sdk import model_registry as mr

    mr.cli_id("agent")     # -> "claude-sonnet-4-6"
    mr.api_id("bulk")      # -> "claude-haiku-4-5-20251001"
    mr.flagship_cli_id()   # -> "claude-fable-5"

Env overrides (highest precedence):
    MODEL_TIER_OVERRIDE_<TIER>=<id>  # e.g. MODEL_TIER_OVERRIDE_AGENT=claude-sonnet-4-6
    MODEL_REGISTRY_PATH=/path/to/yaml
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

# Default: config/model-registry.yaml relative to the repo root (3 levels up from
# fleetwright/sdk/model_registry.py → fleetwright/ → repo root → config/)
_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "model-registry.yaml"


class ModelRegistryError(RuntimeError):
    """Registry missing/corrupt or a tier/alias is unknown."""


def registry_path() -> Path:
    return Path(os.environ.get("MODEL_REGISTRY_PATH", str(_DEFAULT_PATH)))


@lru_cache(maxsize=1)
def _load() -> Dict[str, Any]:
    path = registry_path()
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError as e:
        raise ModelRegistryError(
            f"model registry not found at {path} — "
            "set MODEL_REGISTRY_PATH or place config/model-registry.yaml in the repo root"
        ) from e
    except Exception as e:
        raise ModelRegistryError(f"failed to load model registry {path}: {e}") from e
    if not isinstance(data, dict) or "tiers" not in data:
        raise ModelRegistryError(f"model registry {path} is malformed (no 'tiers' key)")
    return data


def reload() -> None:
    """Drop the cache (tests / long-lived daemons after a registry edit)."""
    _load.cache_clear()


def tiers() -> Dict[str, Dict[str, Any]]:
    return dict(_load()["tiers"])


def tier(name: str) -> Dict[str, Any]:
    t = _load()["tiers"].get(name)
    if not isinstance(t, dict):
        raise ModelRegistryError(
            f"unknown model tier {name!r} (have: {sorted(_load()['tiers'])})"
        )
    return t


def _override(name: str) -> Optional[str]:
    return os.environ.get(f"MODEL_TIER_OVERRIDE_{name.upper()}") or None


def cli_id(name: str) -> str:
    """The exact id `claude --model` accepts for this tier (env-overridable)."""
    ov = _override(name)
    if ov:
        return ov
    v = tier(name).get("cli_id")
    if not v:
        raise ModelRegistryError(f"tier {name!r} has no cli_id")
    return str(v)


def api_id(name: str) -> str:
    """The Anthropic Messages API id for this tier (env-overridable)."""
    ov = _override(name)
    if ov:
        return ov
    v = tier(name).get("api_id") or tier(name).get("cli_id")
    if not v:
        raise ModelRegistryError(f"tier {name!r} has no api_id/cli_id")
    return str(v)


def openrouter_id(name: str) -> Optional[str]:
    v = tier(name).get("openrouter_id")
    return str(v) if v else None


def flagship_tier() -> str:
    return str(_load().get("flagship_tier", "flagship"))


def flagship_cli_id() -> str:
    return cli_id(flagship_tier())


def _alias_tiers() -> Dict[str, str]:
    aliases = _load().get("aliases") or {}
    out: Dict[str, str] = {}
    for key, tname in aliases.items():
        if tname in _load()["tiers"]:
            out[str(key)] = str(tname)
    return out


def cli_alias_map() -> Dict[str, str]:
    """{alias/legacy id -> current cli_id}."""
    return {alias: cli_id(t) for alias, t in _alias_tiers().items()}


def api_alias_map() -> Dict[str, str]:
    """{alias/legacy id -> current Anthropic API id}."""
    return {alias: api_id(t) for alias, t in _alias_tiers().items()}


def openrouter_map() -> Dict[str, str]:
    """{alias/legacy id -> OpenRouter id} for tiers that have one."""
    out: Dict[str, str] = {}
    for alias, t in _alias_tiers().items():
        orid = openrouter_id(t)
        if orid:
            out[alias] = orid
    return out


def anthropic_fallback_map() -> Dict[str, str]:
    """{openrouter id -> Anthropic API id} for direct-API fallback."""
    out: Dict[str, str] = {}
    for t in _load()["tiers"]:
        orid = openrouter_id(t)
        if orid:
            out[orid] = api_id(t)
    for alias, t in _alias_tiers().items():
        if "/" in alias:
            out.setdefault(alias, api_id(t))
    return out


def all_cli_ids() -> list[str]:
    """Unique cli_ids across tiers."""
    seen: dict[str, None] = {}
    for name in _load()["tiers"]:
        seen.setdefault(cli_id(name), None)
    return list(seen)


def cockpit_models() -> list[Dict[str, Any]]:
    """Ordered cockpit-picker rows: {id, label, blurb, default}."""
    rows = []
    for entry in (_load().get("cockpit") or {}).get("models") or []:
        t = tier(str(entry["tier"]))
        rows.append({
            "id": str(t.get("cockpit_id") or t["cli_id"]),
            "label": str(t.get("label") or t["cli_id"]),
            "blurb": str(t.get("blurb") or ""),
            "default": bool(entry.get("default", False)),
        })
    return rows


if __name__ == "__main__":
    import sys
    import json as _json
    fn = sys.argv[1] if len(sys.argv) > 1 else "flagship_cli_id"
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    f = globals().get(fn)
    if not callable(f):
        print(f"unknown function {fn!r}", file=sys.stderr)
        raise SystemExit(2)
    out = f(arg) if arg is not None else f()
    if isinstance(out, (list, tuple, frozenset)):
        print("\n".join(sorted(out) if isinstance(out, frozenset) else out))
    elif isinstance(out, dict):
        print(_json.dumps(out, indent=2, sort_keys=True))
    else:
        print(out)
