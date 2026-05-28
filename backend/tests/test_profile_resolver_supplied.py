"""
test_profile_resolver_supplied.py - Iteration 3 deliverable 4b.

Exercises profile_resolver's caller-supplied short-circuit branch:
when state['supplied'] is present, the resolver synthesises a minimal,
fully-valid profile that selects (mode='supplied', dispatch='draps_v1') and
SKIPS the disk-based candidate-list scan entirely.

Scope (resolver + an end-to-end pass through N3c validator):
  - Synthesised profile has the exact shape the handoff specifies.
  - profile.supplied block carries '_rate'-suffixed keys translated from
    state['supplied'] (state-level swap_now_fixed -> profile-level
    swap_now_fixed_rate). The two naming conventions co-exist; this bridge
    only happens here.
  - profile_resolution_path is the synthesis marker, not a disk path.
  - business_identity is still derived from state.public_market_context so
    the audit trail retains the corridor/commodity snapshot.
  - Disk is NOT touched on the supplied path: a monkeypatched
    _PROFILES_ROOT pointing at a nonexistent directory does NOT cause the
    supplied path to fail.
  - Regression: state without 'supplied' still uses the existing disk-based
    path (returns the india-us-textiles 3-layer merge unchanged).
  - End-to-end: the synthesised profile passes N3c profile_spec_validator
    when wired with the existing supplied-rates-example hedge spec.

NO live services required - pure file I/O + Python. Safe to run in CI.

RUN:
    cd backend
    .venv\\Scripts\\activate
    pytest tests/test_profile_resolver_supplied.py -v
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

import profile_resolver  # noqa: E402  - for monkeypatching _PROFILES_ROOT
from profile_resolver import (  # noqa: E402
    _synthesize_caller_supplied_profile,
    profile_resolver_node,
)
from profile_spec_validator import profile_spec_validator_node  # noqa: E402


# -----------------------------------------------------------------------------
# Shared fixtures
# -----------------------------------------------------------------------------

# State-level supplied block: short key names (no '_rate' suffix). This is
# what the API request handler lifts from POST /run into state['supplied'],
# and what composer._validate_supplied_block enforces.
SAMPLE_SUPPLIED_STATE_LEVEL = {
    "sofr_path": [
        {"time": "2026-02-28T00:00:00", "value": 0.0602},
        {"time": "2026-05-31T00:00:00", "value": 0.0655},
        {"time": "2026-08-31T00:00:00", "value": 0.0704},
    ],
    "swap_now_fixed":   0.0502,
    "swap_later_fixed": 0.0585,
}

# A representative public_market_context. The supplied path still derives
# business_identity from this, so we exercise both the supplied short-circuit
# AND the identity-derivation step in the same test.
STATE_IN_US_TEX = {
    "public_market_context": {
        "corridor": {"origin": "IN", "destination": "US"},
        "gtap_commodity_code": "tex",
    },
    "audit_log": [],
}


def _state_with_supplied(**overrides) -> dict[str, Any]:
    """Build a fresh state dict carrying a 'supplied' block + a market context."""
    s = copy.deepcopy(STATE_IN_US_TEX)
    s["supplied"] = copy.deepcopy(SAMPLE_SUPPLIED_STATE_LEVEL)
    s.update(overrides)
    return s


# -----------------------------------------------------------------------------
# Synthesis: profile shape exactly matches the handoff contract
# -----------------------------------------------------------------------------

def test_synthesis_helper_returns_handoff_shape():
    """The synthesis helper returns the exact five-field shape the handoff specifies."""
    profile = _synthesize_caller_supplied_profile(SAMPLE_SUPPLIED_STATE_LEVEL)

    # Top-level fields per the handoff:
    #   {profile_id, version, mode, dispatch, hedge_spec_id}  (+ supplied for validator)
    assert profile["profile_id"]    == "caller_supplied"
    assert profile["version"]       == "1.0.0"
    assert profile["mode"]          == "supplied"
    assert profile["dispatch"]      == "draps_v1"
    assert profile["hedge_spec_id"] == "supplied-rates-example"


def test_synthesis_translates_key_names_with_rate_suffix():
    """state-level 'swap_now_fixed' -> profile-level 'swap_now_fixed_rate' (with _rate)."""
    profile = _synthesize_caller_supplied_profile(SAMPLE_SUPPLIED_STATE_LEVEL)
    supplied_block = profile["supplied"]

    # Note: profile.supplied uses '_rate'-suffixed keys per the JSON schema.
    # state['supplied'] uses short names. The synthesis bridges the two.
    assert supplied_block["swap_now_fixed_rate"]   == 0.0502
    assert supplied_block["swap_later_fixed_rate"] == 0.0585

    # Short-name keys must NOT appear in the profile block (the schema's
    # additionalProperties:false would reject them).
    assert "swap_now_fixed"   not in supplied_block
    assert "swap_later_fixed" not in supplied_block


def test_synthesis_carries_sofr_path_verbatim():
    """Each {time, value} point flows through to profile.supplied.sofr_path."""
    profile = _synthesize_caller_supplied_profile(SAMPLE_SUPPLIED_STATE_LEVEL)
    path = profile["supplied"]["sofr_path"]

    assert len(path) == 3
    assert path[0] == {"time": "2026-02-28T00:00:00", "value": 0.0602}
    assert path[1] == {"time": "2026-05-31T00:00:00", "value": 0.0655}
    assert path[2] == {"time": "2026-08-31T00:00:00", "value": 0.0704}


def test_synthesis_helper_robust_to_missing_sofr_path():
    """A supplied dict missing sofr_path entirely -> empty list, no crash.

    The composer's _validate_supplied_block (called downstream) is the strict
    gate. The synthesis helper just builds something the schema check can
    reject honestly.
    """
    broken = {"swap_now_fixed": 0.05, "swap_later_fixed": 0.06}
    profile = _synthesize_caller_supplied_profile(broken)
    assert profile["supplied"]["sofr_path"] == []


def test_synthesis_helper_robust_to_missing_swap_rates():
    """A supplied dict missing swap rates -> profile.supplied keys are None.

    Downstream JSON Schema check will flag None as non-number; here we just
    confirm the helper does not raise.
    """
    broken = {"sofr_path": [{"time": "t", "value": 0.05}]}
    profile = _synthesize_caller_supplied_profile(broken)
    assert profile["supplied"]["swap_now_fixed_rate"]   is None
    assert profile["supplied"]["swap_later_fixed_rate"] is None


# -----------------------------------------------------------------------------
# Node entry point: short-circuit when state['supplied'] is present
# -----------------------------------------------------------------------------

def test_node_short_circuits_on_supplied_state():
    """state['supplied'] present -> resolved_risk_profile is the synthesised profile."""
    state = _state_with_supplied()
    result = profile_resolver_node(state)

    profile = result["resolved_risk_profile"]
    assert profile is not None
    assert profile["profile_id"] == "caller_supplied"
    assert profile["mode"]       == "supplied"
    assert profile["dispatch"]   == "draps_v1"


def test_node_sets_resolution_path_to_marker():
    """profile_resolution_path is the synthesis marker, not a disk path."""
    result = profile_resolver_node(_state_with_supplied())
    assert result["profile_resolution_path"] == ["<synthesized: caller_supplied>"]


def test_node_sets_risk_factor_profile_id_to_caller_supplied():
    """state.risk_factor_profile_id is 'caller_supplied' (matches synthesised profile_id)."""
    result = profile_resolver_node(_state_with_supplied())
    assert result["risk_factor_profile_id"] == "caller_supplied"


def test_node_derives_business_identity_even_on_supplied_path():
    """business_identity is still derived from market_context on the supplied path.

    This preserves the corridor/commodity snapshot in the audit log so a
    supplied-mode run is just as traceable as a derived-mode one.
    """
    result = profile_resolver_node(_state_with_supplied())
    identity = result["business_identity"]
    assert identity["mode"]            == "export_import"
    assert identity["exporter"]        == "IN"
    assert identity["importer"]        == "US"
    assert identity["commodity_gtap"]  == "tex"


def test_node_audit_log_records_synthesis_marker():
    """The audit_log entry surfaces synthesis_marker + the synthesised metadata."""
    result = profile_resolver_node(_state_with_supplied())
    entries = result["audit_log"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["node"] == "profile_resolver"
    assert "synthesi" in entry["summary"].lower()  # 'synthesised' or 'synthesized'

    out = entry["output"]
    assert out["synthesis_marker"] == "caller_supplied"
    assert out["profile_id"]       == "caller_supplied"
    assert out["mode"]             == "supplied"
    assert out["dispatch"]         == "draps_v1"
    assert out["hedge_spec_id"]    == "supplied-rates-example"


def test_node_does_not_set_validation_errors_on_synthesis_path():
    """Synthesis is success; no validation_errors are produced."""
    result = profile_resolver_node(_state_with_supplied())
    assert "validation_errors" not in result or not result.get("validation_errors")


# -----------------------------------------------------------------------------
# Disk-not-touched: a broken _PROFILES_ROOT cannot affect the supplied path
# -----------------------------------------------------------------------------

def test_supplied_path_does_not_touch_disk(monkeypatch, tmp_path):
    """Point _PROFILES_ROOT at a nonexistent dir; supplied path must still succeed.

    If the resolver were calling _scan_candidates on the supplied path, this
    test would fail with a 'profiles directory not found' validation_error.
    Success here proves the disk branch is skipped.
    """
    bogus_root = tmp_path / "does_not_exist"
    monkeypatch.setattr(profile_resolver, "_PROFILES_ROOT", bogus_root)

    result = profile_resolver_node(_state_with_supplied())

    assert result["resolved_risk_profile"] is not None
    assert result["resolved_risk_profile"]["profile_id"] == "caller_supplied"
    assert not result.get("validation_errors")


# -----------------------------------------------------------------------------
# Regression: state without 'supplied' still uses the disk-based path
# -----------------------------------------------------------------------------

def test_supplied_absent_still_uses_disk_based_resolution():
    """state with no 'supplied' key -> existing IN-US-tex three-layer merge."""
    state = copy.deepcopy(STATE_IN_US_TEX)  # no 'supplied' key
    result = profile_resolver_node(state)

    assert result["risk_factor_profile_id"] == "india-us-textiles-v1"
    paths = result["profile_resolution_path"]
    assert len(paths) == 3  # commodity + corridor + base
    assert "india-us-textiles.json" in paths[0]
    assert "india-us.json"          in paths[1]
    assert "_base.json"             in paths[2]


def test_supplied_none_still_uses_disk_based_resolution():
    """state with 'supplied': None is treated the same as 'supplied' absent."""
    state = copy.deepcopy(STATE_IN_US_TEX)
    state["supplied"] = None
    result = profile_resolver_node(state)

    # Same outcome as the absent case: real disk-based 3-layer resolution.
    assert result["risk_factor_profile_id"] == "india-us-textiles-v1"
    assert len(result["profile_resolution_path"]) == 3


# -----------------------------------------------------------------------------
# End-to-end: synthesised profile passes N3c profile_spec_validator
#
# The handoff requires: "The N3c profile_spec_validator must accept this
# synthesised profile - confirm by re-running test_profile_spec_validator.py."
# That existing file's tests still run on the derived india-us-textiles
# profile (no 'supplied' key in their STATE_IN_US_TEX), so they remain green
# unchanged. THIS test directly proves the synthesised profile clears N3c.
# -----------------------------------------------------------------------------

def test_synthesised_profile_passes_n3c_validator():
    """End-to-end: resolver short-circuit -> N3c -> no validation_errors.

    Wires the synthesised profile with the existing supplied-rates-example
    hedge spec (loaded directly from disk; we don't run the N3b stub here
    because it currently still returns _default.json regardless of
    hedge_spec_id - that's outside this deliverable's scope).
    """
    state = _state_with_supplied()
    state.update(profile_resolver_node(state))

    # Load the existing supplied-rates-example hedge spec from disk.
    spec_path = REPO_ROOT / "config" / "hedge-specs" / "supplied-rates-example.json"
    assert spec_path.is_file(), (
        f"missing prerequisite from deliverable 1: {spec_path}. "
        "Re-run config/hedge-specs/supplied-rates-example.json author step."
    )
    with spec_path.open("r", encoding="utf-8") as f:
        state["resolved_hedge_spec"] = json.load(f)
    state["hedge_spec_id"] = state["resolved_hedge_spec"]["spec_id"]

    result = profile_spec_validator_node(state)
    errors = result.get("validation_errors")
    assert not errors, (
        f"synthesised profile failed N3c validation: {errors}. "
        "The synthesis or the validator's contract drifted."
    )


def test_synthesised_profile_jsonschema_passes():
    """The synthesised profile clears the risk-factor-profile JSON Schema by itself.

    Independent of the N3c node wrapper; lets us pinpoint a schema regression
    without needing the hedge spec or upstream state.
    """
    from jsonschema import Draft202012Validator  # local import; jsonschema is a project dep

    schema_path = REPO_ROOT / "schemas" / "risk-factor-profile.schema.json"
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)

    profile = _synthesize_caller_supplied_profile(SAMPLE_SUPPLIED_STATE_LEVEL)
    errors = list(Draft202012Validator(schema).iter_errors(profile))
    assert not errors, (
        "synthesised profile failed JSON Schema check: "
        + "; ".join(f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors)
    )
