"""
hedge_spec_resolver.py — N3b Hedge-Spec Resolver.

ITERATION-1 STUB. Hardcoded load of config/hedge-specs/_default.json.
Real selection logic (per-profile, per-customer, per-request override) lands in Iteration 3+.

CONTRACT (Iteration 1):
  Reads  state.resolved_risk_profile (to honour a future `hedge_spec_id` field)
  Writes state.hedge_spec_id, state.resolved_hedge_spec

NO LLM IMPORTS \u2014 deterministic by design (agent-type law).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent

_DEFAULT_SPEC_PATH = _REPO_ROOT / "config" / "hedge-specs" / "_default.json"


def _audit_entry(node: str, summary: str, output: dict[str, Any]) -> dict[str, Any]:
    return {
        "node": node,
        "summary": summary,
        "output": output,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def hedge_spec_resolver_node(state: dict) -> dict:
    """N3b \u2014 deterministic. Resolve the hedge spec for this run.

    Iteration-1 behaviour: always returns hedge-specs/_default.json.
    The profile's optional `hedge_spec_id` field is honoured in Iteration 3+;
    request-level supplied overrides also land in Iteration 3.
    """
    profile = state.get("resolved_risk_profile") or {}
    requested_id = profile.get("hedge_spec_id")  # may be None in Iteration 1

    if not _DEFAULT_SPEC_PATH.is_file():
        raise FileNotFoundError(
            f"Iteration-1 hardcoded hedge spec not found at {_DEFAULT_SPEC_PATH}. "
            "Re-run Step 6 of the iteration plan to author the spec."
        )

    with _DEFAULT_SPEC_PATH.open("r", encoding="utf-8") as f:
        spec = json.load(f)

    spec_id = spec.get("spec_id", "unknown")
    return {
        "hedge_spec_id": spec_id,
        "resolved_hedge_spec": spec,
        "audit_log": [
            _audit_entry(
                "hedge_spec_resolver",
                f"loaded hedge spec {spec_id} (hardcoded stub)",
                {
                    "spec_id": spec_id,
                    "requested_id": requested_id,
                    "source": str(_DEFAULT_SPEC_PATH.relative_to(_REPO_ROOT)),
                },
            )
        ],
    }
