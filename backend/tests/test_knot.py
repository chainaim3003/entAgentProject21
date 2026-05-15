"""
test_knot.py — Deterministic-core regression.

Two layers:
  1. Validator (N3) — pure code, fully testable now.
  2. Simulation (N4) — wraps DRAPS; skipped with reason until the DRAPS contract is verified.

The validator tests are the eval gate for the boundary. Every commit MUST keep them green.
The simulation test is the proof that the knot is reproducible: same input -> same A/B/C totals.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

import pytest

# Make backend/ importable when running `pytest backend/tests/`
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Validator tests don't need GEMINI_API_KEY etc. Provide stubs so config.py loads.
os.environ.setdefault("GEMINI_API_KEY", "test-not-used")
os.environ.setdefault("DRAPS_MCP_URL", "http://test-not-used")
os.environ.setdefault("ACTUS_MENTOR_URL", "http://test-not-used")

from deterministic_agents import validator_node  # noqa: E402


# ───────────────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────────────

@pytest.fixture
def clean_state() -> dict:
    """A state where validation should pass."""
    return {
        "raw_inputs": {
            "notional_usd": 1_000_000,
            "spread_bps": 250,
            "term_months": 24,
            "start_date": "2026-01-15",
            "rate_index": "SOFR",
            "commodity_hint": "textiles imported from India",
            "corridor_hint": "India to US",
        },
        "market_context": {
            "gtap_commodity_code": "50",
            "corridor": {"origin": "IN", "destination": "US"},
            "tariff_assumption_pct": 0.25,
            "rate_curve_index": "USD-SOFR-FORWARD",
            "notes": "textiles HS50",
        },
        "audit_log": [],
        "retry_count": 0,
    }


# ───────────────────────────────────────────────────────────────────────
# Validator: success cases
# ───────────────────────────────────────────────────────────────────────

def test_validator_passes_clean_inputs(clean_state):
    out = validator_node(clean_state)
    assert out["validation_errors"] == []
    assert "validated_inputs" in out
    v = out["validated_inputs"]
    # Single producer / canonical shape
    assert set(v.keys()) == {"loan", "market"}
    assert v["loan"]["notional_usd"] == 1_000_000.0
    assert v["loan"]["term_months"] == 24
    assert v["market"]["corridor"] == {"origin": "IN", "destination": "US"}


def test_validator_is_deterministic(clean_state):
    """Same input -> same output. Boundary invariant."""
    a = validator_node(clean_state)
    b = validator_node(clean_state)
    assert a["validated_inputs"] == b["validated_inputs"]
    assert a["validation_errors"] == b["validation_errors"]


# ───────────────────────────────────────────────────────────────────────
# Validator: failure cases
# ───────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "patch, expected_substr",
    [
        ({"notional_usd": -1}, "notional_usd: must be > 0"),
        ({"notional_usd": "lots"}, "notional_usd: must be a number"),
        ({"notional_usd": 2_000_000_000}, "implausibly large"),
        ({"spread_bps": -10}, "spread_bps: out of range"),
        ({"spread_bps": 10000}, "spread_bps: out of range"),
        ({"term_months": 0}, "term_months: out of range"),
        ({"term_months": 24.5}, "term_months: must be an integer"),
        ({"start_date": "yesterday"}, "not a valid ISO 8601"),
        ({"rate_index": ""}, "rate_index: must be a non-empty string"),
    ],
)
def test_validator_rejects_bad_intake(clean_state, patch, expected_substr):
    state = dict(clean_state)
    state["raw_inputs"] = {**clean_state["raw_inputs"], **patch}
    out = validator_node(state)
    assert out["validation_errors"], "expected validation errors"
    assert "validated_inputs" not in out
    assert any(expected_substr in e for e in out["validation_errors"])


@pytest.mark.parametrize(
    "patch, expected_substr",
    [
        ({"gtap_commodity_code": ""}, "gtap_commodity_code: must be a non-empty string"),
        ({"corridor": None}, "corridor: must be"),
        ({"corridor": {"origin": "IN"}}, "corridor: must be"),
        ({"tariff_assumption_pct": 10.0}, "tariff_assumption_pct: out of range"),
        ({"rate_curve_index": ""}, "rate_curve_index: must be a non-empty string"),
    ],
)
def test_validator_rejects_bad_market_context(clean_state, patch, expected_substr):
    state = dict(clean_state)
    state["market_context"] = {**clean_state["market_context"], **patch}
    out = validator_node(state)
    assert out["validation_errors"], "expected validation errors"
    assert any(expected_substr in e for e in out["validation_errors"])


# ───────────────────────────────────────────────────────────────────────
# Validator: audit log invariant (I3)
# ───────────────────────────────────────────────────────────────────────

def test_validator_appends_audit_entry(clean_state):
    out = validator_node(clean_state)
    assert "audit_log" in out
    assert len(out["audit_log"]) == 1
    entry = out["audit_log"][0]
    assert entry["node"] == "validator"
    assert "ts" in entry
    # ts is a valid ISO timestamp
    datetime.fromisoformat(entry["ts"])


# ───────────────────────────────────────────────────────────────────────
# Simulation (N4 — the knot) — gated on DRAPS contract being implemented
# ───────────────────────────────────────────────────────────────────────

def _draps_is_implemented() -> bool:
    """Check whether draps_client.run_simulation has been wired up beyond the placeholder."""
    try:
        import draps_client  # noqa: F401
        from deterministic_agents import simulation_node
        # Smoke call: if it still raises NotImplementedError, treat as not-implemented.
        simulation_node({"validated_inputs": {"loan": {}, "market": {}}})
    except NotImplementedError:
        return False
    except Exception:
        # Some other error (e.g. real network failure) — counts as "implemented but failing".
        return True
    return True


@pytest.mark.skipif(
    not _draps_is_implemented(),
    reason=(
        "DRAPS run_simulation not yet implemented. "
        "See DESIGN/DESIGN1/design-1-detailed-design.md §6 note 1."
    ),
)
def test_simulation_is_reproducible(clean_state):
    """Same validated_inputs -> same A/B/C totals. Knot is deterministic."""
    from deterministic_agents import simulation_node

    validated = validator_node(clean_state)["validated_inputs"]
    state = {"validated_inputs": validated, "audit_log": []}

    out1 = simulation_node(state)
    out2 = simulation_node(state)

    assert out1["simulation_result"]["A_total"] == out2["simulation_result"]["A_total"]
    assert out1["simulation_result"]["B_total"] == out2["simulation_result"]["B_total"]
    assert out1["simulation_result"]["C_total"] == out2["simulation_result"]["C_total"]


@pytest.mark.skipif(
    not _draps_is_implemented(),
    reason="DRAPS run_simulation not yet implemented.",
)
def test_simulation_never_reads_prompt(clean_state):
    """Invariant I1: simulation must not depend on the prompt.

    Two different prompts, same validated_inputs -> identical simulation_result.
    """
    from deterministic_agents import simulation_node

    validated = validator_node(clean_state)["validated_inputs"]

    state_a = {"validated_inputs": validated, "prompt": "should I hedge?", "audit_log": []}
    state_b = {"validated_inputs": validated, "prompt": "tell me a joke", "audit_log": []}

    out_a = simulation_node(state_a)
    out_b = simulation_node(state_b)

    assert out_a["simulation_result"] == out_b["simulation_result"]
