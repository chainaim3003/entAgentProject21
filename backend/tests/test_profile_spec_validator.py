"""
test_profile_spec_validator.py \u2014 Iteration 2 deliverable 6.

Exercises the real profile_spec_validator per design-v1-config-architecture.md \u00a76:
JSON Schema checks (1, 2) + cross-file checks (3) + mode invariants (4).
Tests use the real resolver/hedge-spec-resolver output as the baseline, then
mutate the merged profile/spec in memory to synthesise failure cases.

NO live services required \u2014 pure file I/O + Python. Safe to run in CI.

RUN:
    cd backend
    .venv\\Scripts\\activate
    pytest tests/test_profile_spec_validator.py -v
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
sys.path.insert(0, str(BACKEND_DIR))

from hedge_spec_resolver import hedge_spec_resolver_node  # noqa: E402
from profile_resolver import profile_resolver_node  # noqa: E402
from profile_spec_validator import profile_spec_validator_node  # noqa: E402


STATE_IN_US_TEX = {
    "public_market_context": {
        "corridor": {"origin": "IN", "destination": "US"},
        "gtap_commodity_code": "tex",
    },
    "audit_log": [],
}


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Fixture: a fully-resolved state with valid profile + spec, deep-copied per test
# so mutations don't leak.
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@pytest.fixture
def resolved_state() -> dict[str, Any]:
    """Build a fresh fully-resolved state for each test."""
    s = copy.deepcopy(STATE_IN_US_TEX)
    s.update(profile_resolver_node(s))
    s.update(hedge_spec_resolver_node(s))
    return s


def _get_component(profile: dict, name: str) -> dict:
    for c in profile.get("components") or []:
        if c.get("name") == name:
            return c
    raise AssertionError(f"component {name!r} not found in profile")


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Happy path
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def test_valid_profile_and_spec_pass(resolved_state):
    """No errors with the real india-us-textiles profile + _default hedge spec."""
    result = profile_spec_validator_node(resolved_state)
    assert result.get("validation_errors") is None
    assert "\u2713" in result["audit_log"][0]["summary"]


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Cross-file check 3a: formula_id existence
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def test_missing_formula_id_file_is_rejected(resolved_state):
    """A profile referencing a nonexistent component file \u2192 validation_errors."""
    _get_component(resolved_state["resolved_risk_profile"], "tariff")["formula_id"] = (
        "nonexistent_formula_xyz"
    )
    result = profile_spec_validator_node(resolved_state)
    errors = result.get("validation_errors") or []
    assert any("nonexistent_formula_xyz" in e and "no file" in e for e in errors), (
        f"expected formula_id-not-found error; got {errors}"
    )


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Cross-file check 3b: inputs vs inputs_schema (type, bounds, nested objects)
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def test_input_value_below_min_is_rejected(resolved_state):
    """tariff_current_pct = -1 violates min 0 in tariff_gtap_quadratic.inputs_schema."""
    tariff = _get_component(resolved_state["resolved_risk_profile"], "tariff")
    tariff["inputs"]["tariff_current_pct"] = -1
    result = profile_spec_validator_node(resolved_state)
    errors = result.get("validation_errors") or []
    assert any("tariff_current_pct" in e and "min" in e for e in errors), (
        f"expected min-violation error; got {errors}"
    )


def test_input_value_above_max_is_rejected(resolved_state):
    """armington_elasticity = 100 violates max 20."""
    tariff = _get_component(resolved_state["resolved_risk_profile"], "tariff")
    tariff["inputs"]["armington_elasticity"] = 100
    result = profile_spec_validator_node(resolved_state)
    errors = result.get("validation_errors") or []
    assert any("armington_elasticity" in e and "max" in e for e in errors), (
        f"expected max-violation error; got {errors}"
    )


def test_undeclared_input_key_is_rejected(resolved_state):
    """An input key not declared in the component's inputs_schema is flagged."""
    tariff = _get_component(resolved_state["resolved_risk_profile"], "tariff")
    tariff["inputs"]["extra_unknown_param"] = 42
    result = profile_spec_validator_node(resolved_state)
    errors = result.get("validation_errors") or []
    assert any(
        "extra_unknown_param" in e and "not declared" in e for e in errors
    ), f"expected undeclared-key error; got {errors}"


def test_nested_object_input_validated(resolved_state):
    """stress_timing.months_to_peak with a string value is flagged at the nested path."""
    tariff = _get_component(resolved_state["resolved_risk_profile"], "tariff")
    tariff["inputs"]["stress_timing"]["months_to_peak"] = "twelve"  # should be integer
    result = profile_spec_validator_node(resolved_state)
    errors = result.get("validation_errors") or []
    assert any(
        "months_to_peak" in e and ("integer" in e or "expected" in e) for e in errors
    ), f"expected nested-type error; got {errors}"


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Mode invariants (check 4)
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def test_mode_derived_without_components_is_rejected(resolved_state):
    """mode=derived with empty components[] \u2192 mode invariant fail."""
    resolved_state["resolved_risk_profile"]["components"] = []
    result = profile_spec_validator_node(resolved_state)
    errors = result.get("validation_errors") or []
    assert any(
        "derived" in e and "components" in e for e in errors
    ), f"expected mode-invariant error; got {errors}"


def test_supplied_block_with_derived_mode_is_rejected(resolved_state):
    """mode=derived + a supplied block (mutually exclusive) \u2192 fail."""
    resolved_state["resolved_risk_profile"]["supplied"] = {
        "sofr_path": [{"time": "2026-01-01", "value": 0.05}],
        "swap_now_fixed_rate": 0.05,
        "swap_later_fixed_rate": 0.06,
    }
    result = profile_spec_validator_node(resolved_state)
    errors = result.get("validation_errors") or []
    assert any(
        "mutually exclusive" in e or ("derived" in e and "supplied" in e)
        for e in errors
    ), f"expected mutual-exclusion error; got {errors}"


def test_unknown_mode_is_rejected(resolved_state):
    """An unrecognised mode value \u2192 fail."""
    resolved_state["resolved_risk_profile"]["mode"] = "frobnicated"
    result = profile_spec_validator_node(resolved_state)
    errors = result.get("validation_errors") or []
    assert any(
        "frobnicated" in e or "unknown mode" in e for e in errors
    ), f"expected unknown-mode error; got {errors}"


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# JSON Schema (checks 1 + 2)
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def test_profile_schema_rejects_unknown_top_level_key(resolved_state):
    """additionalProperties: false on the profile schema catches typos / stale fields."""
    resolved_state["resolved_risk_profile"]["unknown_top_field_typo"] = "x"
    result = profile_spec_validator_node(resolved_state)
    errors = result.get("validation_errors") or []
    assert any(
        "profile schema" in e
        and ("unknown_top_field_typo" in e or "additional" in e.lower())
        for e in errors
    ), f"expected schema-additionalProperties error; got {errors}"


def test_hedge_spec_schema_rejects_missing_required(resolved_state):
    """Removing spec_id (required) trips the hedge-spec schema check."""
    del resolved_state["resolved_hedge_spec"]["spec_id"]
    result = profile_spec_validator_node(resolved_state)
    errors = result.get("validation_errors") or []
    assert any(
        "hedge-spec schema" in e and "spec_id" in e for e in errors
    ), f"expected schema-required error; got {errors}"


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Carry-forward: upstream errors propagate to give_up
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def test_upstream_validation_errors_propagate(resolved_state):
    """Errors from N3a carry through N3c unchanged when no new errors arise."""
    resolved_state["validation_errors"] = ["profile_resolver: simulated upstream error"]
    result = profile_spec_validator_node(resolved_state)
    errors = result.get("validation_errors") or []
    assert "profile_resolver: simulated upstream error" in errors
    # No new errors on a valid profile
    assert len(errors) == 1


def test_upstream_errors_combine_with_new_errors(resolved_state):
    """Upstream + new errors both appear in the output, upstream first."""
    resolved_state["validation_errors"] = ["upstream: earlier error"]
    _get_component(resolved_state["resolved_risk_profile"], "tariff")["formula_id"] = (
        "nonexistent_formula_xyz"
    )
    result = profile_spec_validator_node(resolved_state)
    errors = result.get("validation_errors") or []
    assert "upstream: earlier error" in errors
    assert any("nonexistent_formula_xyz" in e for e in errors)
    assert errors[0] == "upstream: earlier error"  # ordering: upstream first


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Validator accumulates ALL errors (no short-circuit)
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def test_multiple_errors_accumulated_not_short_circuited(resolved_state):
    """Three independent breakages \u2192 at least 3 errors surfaced in one pass."""
    p = resolved_state["resolved_risk_profile"]
    # 1. unknown mode
    p["mode"] = "frobnicated"
    # 2. bad formula_id on base_sofr
    _get_component(p, "base_sofr")["formula_id"] = "nonexistent_a"
    # 3. undeclared input on tariff
    _get_component(p, "tariff")["inputs"]["mystery_param"] = 1
    result = profile_spec_validator_node(resolved_state)
    errors = result.get("validation_errors") or []
    assert len(errors) >= 3, (
        f"expected \u22653 errors (no short-circuit); got {len(errors)}: {errors}"
    )
