"""
test_composer_supplied.py — Iteration 3 deliverable 3.

Unit-tests the composer's `mode='supplied'` dispatch path per
design-v1-iteration-plan.md §"ITERATION 3 — Supplied Mode (Problem A)".

Scope (composer only — no graph, no DRAPS, no ACTUS):
  • Happy path: caller's SOFR path + fixed rates flow into knot_payload verbatim
    with deep-copy semantics (downstream mutation cannot leak back to caller state).
  • Provenance stamp records mode='supplied' and carries a source_summary that
    clearly distinguishes supplied numbers from derived ones.
  • Audit log records the supplied metadata (point count, fixed rates) so the
    UI/SSE trace can show what was supplied without re-reading the payload.
  • Honest failure on every shape violation — missing block, missing keys,
    wrong types, empty path, malformed path points. No silent defaults.
  • Regression: mode='derived' + dispatch='draps_v1' still produces the Iter-1
    shape with no 'supplied' key in knot_payload and mode='derived' in provenance.
  • Unsupported (mode, dispatch) combinations raise NotImplementedError with a
    message naming the supported combinations.

NO live services required — pure Python. Safe to run in CI.

RUN:
    cd backend
    .venv\\Scripts\\activate
    pytest tests/test_composer_supplied.py -v
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
sys.path.insert(0, str(BACKEND_DIR))

from composer import (  # noqa: E402
    SUPPLIED_REQUIRED_KEYS,
    _validate_supplied_block,
    composer_node,
)


# ───────────────────────────────────────────────────────────────────────
# Shared fixtures / sample data
# ───────────────────────────────────────────────────────────────────────

# Minimal but realistic validated_inputs — matches the shape of the V1 baseline
# fixture (backend/tests/fixtures/v1-baseline/india-us-textiles.json).
SAMPLE_VALIDATED_INPUTS = {
    "loan": {
        "notional_usd": 1_000_000.0,
        "spread_bps": 250.0,
        "term_months": 24,
        "start_date": "2026-03-01",
        "rate_index": "SOFR",
    },
    "market": {
        "gtap_commodity_code": "tex",
        "corridor": {"origin": "India", "destination": "United States"},
        "tariff_assumption_pct": 0.5,
        "rate_curve_index": "USD-SOFR-FORWARD",
    },
}

# Three-point SOFR path. Enough to exercise list semantics without bulk;
# values mirror the first three points of the V2-locked baseline curve.
SAMPLE_SUPPLIED = {
    "sofr_path": [
        {"time": "2026-02-28T00:00:00", "value": 0.0602},
        {"time": "2026-05-31T00:00:00", "value": 0.0655},
        {"time": "2026-08-31T00:00:00", "value": 0.0704},
    ],
    "swap_now_fixed":   0.0502,
    "swap_later_fixed": 0.0585,
}

# A profile that selects mode='supplied' + dispatch='draps_v1'. Iteration 3 wires
# this combination as the only supported supplied-mode dispatch.
SUPPLIED_PROFILE = {
    "profile_id": "test-supplied-india-us-textiles",
    "mode": "supplied",
    "dispatch": "draps_v1",
}

# The Iter-1 derived profile, for regression tests.
DERIVED_PROFILE = {
    "profile_id": "india-us-textiles-v1",
    "mode": "derived",
    "dispatch": "draps_v1",
}

SUPPLIED_SPEC = {"spec_id": "supplied-rates-example"}
DERIVED_SPEC = {"spec_id": "default-3-scenario"}


def _make_supplied_state(**overrides):
    """Build a clean state dict for mode='supplied' tests. Overrides override.

    Returns deep copies of the module-level constants so per-test mutations
    cannot leak across tests (defensive against pytest reordering).
    """
    state = {
        "validated_inputs": copy.deepcopy(SAMPLE_VALIDATED_INPUTS),
        "resolved_risk_profile": copy.deepcopy(SUPPLIED_PROFILE),
        "resolved_hedge_spec": copy.deepcopy(SUPPLIED_SPEC),
        "supplied": copy.deepcopy(SAMPLE_SUPPLIED),
    }
    state.update(overrides)
    return state


def _make_derived_state(**overrides):
    """Build a clean state dict for the Iter-1 derived regression tests."""
    state = {
        "validated_inputs": copy.deepcopy(SAMPLE_VALIDATED_INPUTS),
        "resolved_risk_profile": copy.deepcopy(DERIVED_PROFILE),
        "resolved_hedge_spec": copy.deepcopy(DERIVED_SPEC),
    }
    state.update(overrides)
    return state


# ───────────────────────────────────────────────────────────────────────
# Happy path
# ───────────────────────────────────────────────────────────────────────

def test_supplied_mode_happy_path():
    """mode=supplied + dispatch=draps_v1 + valid supplied block → knot_payload built."""
    result = composer_node(_make_supplied_state())

    assert "knot_payload" in result
    assert "audit_log" in result
    kp = result["knot_payload"]
    assert kp is not None
    # The supplied block lives on the knot_payload.
    assert "supplied" in kp
    # Plus the validated_inputs structure is preserved.
    assert "loan" in kp
    assert "market" in kp
    # Plus the provenance stamp.
    assert "_provenance" in kp


def test_supplied_sofr_path_carried_verbatim_and_deep_copied():
    """SOFR path on knot_payload equals input; mutating input does not leak."""
    state = _make_supplied_state()
    result = composer_node(state)

    kp_path = result["knot_payload"]["supplied"]["sofr_path"]
    assert kp_path == SAMPLE_SUPPLIED["sofr_path"], "path values must round-trip"
    assert len(kp_path) == 3

    # Deep-copy check: mutating the source state's path must NOT mutate knot_payload.
    state["supplied"]["sofr_path"][0]["value"] = 0.9999
    assert result["knot_payload"]["supplied"]["sofr_path"][0]["value"] == 0.0602, (
        "composer must deep-copy the supplied block; caller mutations leaked through"
    )


def test_supplied_fixed_rates_carried_verbatim():
    """swap_now_fixed and swap_later_fixed flow into knot_payload unchanged."""
    result = composer_node(_make_supplied_state())

    s = result["knot_payload"]["supplied"]
    assert s["swap_now_fixed"]   == 0.0502
    assert s["swap_later_fixed"] == 0.0585


def test_supplied_knot_payload_preserves_validated_inputs():
    """knot_payload carries loan + market from validated_inputs, deep-copied.

    Mutating the same state that went into the composer must NOT affect the
    composer's output — this is the deep-copy contract for validated_inputs.
    """
    state = _make_supplied_state()
    result = composer_node(state)
    kp = result["knot_payload"]

    assert kp["loan"]["spread_bps"] == 250.0
    assert kp["market"]["gtap_commodity_code"] == "tex"

    # Deep-copy check on the SAME state that went into the composer.
    state["validated_inputs"]["loan"]["spread_bps"] = 999.0
    assert result["knot_payload"]["loan"]["spread_bps"] == 250.0, (
        "composer must deep-copy validated_inputs; caller mutations leaked into knot_payload"
    )


# ───────────────────────────────────────────────────────────────────────
# Provenance distinguishes supplied from derived
# ───────────────────────────────────────────────────────────────────────

def test_supplied_provenance_has_mode_and_dispatch_recorded():
    """_provenance stamp carries mode='supplied' + dispatch='draps_v1'."""
    result = composer_node(_make_supplied_state())
    prov = result["knot_payload"]["_provenance"]

    assert prov["mode"] == "supplied"
    assert prov["dispatch"] == "draps_v1"
    assert prov["profile_id"] == "test-supplied-india-us-textiles"
    assert prov["hedge_spec_id"] == "supplied-rates-example"
    # Schema version pinned so downstream consumers can branch safely.
    assert prov["schema_version"] == "1.0.0"


def test_supplied_provenance_source_summary_says_caller_supplied():
    """The source_summary text clearly marks numbers as caller-supplied."""
    result = composer_node(_make_supplied_state())
    summary = result["knot_payload"]["_provenance"]["source_summary"]

    # Distinguishes from the derived path's summary text. The check is loose
    # enough that the wording can be refined later without breaking the test.
    assert "CALLER-SUPPLIED" in summary
    assert "derivation" in summary.lower() or "verbatim" in summary.lower()


# ───────────────────────────────────────────────────────────────────────
# Audit log
# ───────────────────────────────────────────────────────────────────────

def test_supplied_audit_log_records_supplied_metadata():
    """The audit entry surfaces supplied metadata without re-reading the payload."""
    result = composer_node(_make_supplied_state())
    entries = result["audit_log"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["node"] == "composer"

    out = entry["output"]
    assert out["mode"] == "supplied"
    assert out["dispatch"] == "draps_v1"
    assert out["supplied_sofr_path_points"] == 3
    assert out["supplied_swap_now_fixed"]   == 0.0502
    assert out["supplied_swap_later_fixed"] == 0.0585
    # knot_payload_keys list should include 'supplied' alongside the validated keys.
    assert "supplied" in out["knot_payload_keys"]
    assert "loan" in out["knot_payload_keys"]
    assert "market" in out["knot_payload_keys"]


# ───────────────────────────────────────────────────────────────────────
# Honest failure: state['supplied'] missing or malformed
# ───────────────────────────────────────────────────────────────────────

def test_supplied_mode_without_supplied_block_raises():
    """profile says mode=supplied but state lacks 'supplied' → RuntimeError."""
    state = _make_supplied_state()
    del state["supplied"]

    with pytest.raises(RuntimeError, match=r"state\['supplied'\] is missing"):
        composer_node(state)


def test_supplied_block_not_dict_raises():
    """state['supplied'] is a list/str/None → RuntimeError naming the type."""
    state = _make_supplied_state(supplied="not a dict")
    with pytest.raises(RuntimeError, match="must be a dict"):
        composer_node(state)


@pytest.mark.parametrize("missing_key", list(SUPPLIED_REQUIRED_KEYS))
def test_supplied_missing_required_keys_raises(missing_key):
    """Any required key missing from state['supplied'] → RuntimeError naming it."""
    broken = {k: v for k, v in SAMPLE_SUPPLIED.items() if k != missing_key}
    state = _make_supplied_state(supplied=broken)
    with pytest.raises(RuntimeError, match=f"missing required keys.*{missing_key}"):
        composer_node(state)


def test_supplied_sofr_path_not_list_raises():
    """sofr_path is a dict instead of a list → RuntimeError."""
    bad = dict(SAMPLE_SUPPLIED)
    bad["sofr_path"] = {"not": "a list"}
    state = _make_supplied_state(supplied=bad)
    with pytest.raises(RuntimeError, match="sofr_path.*non-empty list"):
        composer_node(state)


def test_supplied_sofr_path_empty_raises():
    """Empty sofr_path → RuntimeError (no silent acceptance of zero points)."""
    bad = dict(SAMPLE_SUPPLIED)
    bad["sofr_path"] = []
    state = _make_supplied_state(supplied=bad)
    with pytest.raises(RuntimeError, match="sofr_path.*non-empty list"):
        composer_node(state)


def test_supplied_sofr_path_point_missing_keys_raises():
    """A path point missing 'time' or 'value' → RuntimeError naming the index."""
    bad = dict(SAMPLE_SUPPLIED)
    bad["sofr_path"] = [
        {"time": "2026-02-28T00:00:00", "value": 0.06},
        {"time": "2026-05-31T00:00:00"},  # value missing
    ]
    state = _make_supplied_state(supplied=bad)
    with pytest.raises(RuntimeError, match=r"sofr_path.*\[1\].*'time' and 'value'"):
        composer_node(state)


def test_supplied_sofr_path_value_non_numeric_raises():
    """A path point's value is a string → RuntimeError."""
    bad = dict(SAMPLE_SUPPLIED)
    bad["sofr_path"] = [{"time": "2026-02-28T00:00:00", "value": "not_a_number"}]
    state = _make_supplied_state(supplied=bad)
    with pytest.raises(RuntimeError, match=r"sofr_path.*\[0\].*'value'.*numeric"):
        composer_node(state)


@pytest.mark.parametrize("rate_key", ["swap_now_fixed", "swap_later_fixed"])
def test_supplied_swap_rate_non_numeric_raises(rate_key):
    """A fixed rate is a string → RuntimeError naming the key."""
    bad = dict(SAMPLE_SUPPLIED)
    bad[rate_key] = "not_a_number"
    state = _make_supplied_state(supplied=bad)
    with pytest.raises(RuntimeError, match=f"{rate_key}.*numeric"):
        composer_node(state)


# ───────────────────────────────────────────────────────────────────────
# Regression: Iter-1 derived path unchanged
# ───────────────────────────────────────────────────────────────────────

def test_derived_mode_still_produces_iter1_shape():
    """mode=derived + dispatch=draps_v1 still passes through with no 'supplied' key."""
    result = composer_node(_make_derived_state())
    kp = result["knot_payload"]

    # Iter-1 contract: knot_payload is a deep copy of validated_inputs + _provenance.
    assert "loan" in kp
    assert "market" in kp
    assert "_provenance" in kp
    # The supplied path is NOT used for derived mode.
    assert "supplied" not in kp

    # The provenance stamp now carries a `mode` field (added in Iter 3) — derived
    # runs must report mode='derived' so downstream consumers can branch on it.
    prov = kp["_provenance"]
    assert prov["mode"] == "derived"
    assert prov["dispatch"] == "draps_v1"
    # Source summary should still describe the derived path (DRAPS-side derivation).
    assert "DRAPS" in prov["source_summary"]


def test_derived_mode_ignores_supplied_in_state():
    """If state happens to carry a 'supplied' block but profile says mode=derived,
    derived path runs as normal and 'supplied' is NOT copied into knot_payload.
    Defensive: the composer must not let stray state cross the mode boundary."""
    state = _make_derived_state(supplied=SAMPLE_SUPPLIED)
    result = composer_node(state)
    assert "supplied" not in result["knot_payload"]


# ───────────────────────────────────────────────────────────────────────
# Dispatch table boundaries
# ───────────────────────────────────────────────────────────────────────

def test_supplied_mode_with_unsupported_dispatch_raises():
    """mode='supplied' pairs only with dispatch='draps_v1'; 'supplied' + 'v2_direct'
    is an unsupported combo (no such branch) → NotImplementedError, no silent
    fallback. (Was 'Iter 4 territory' before 6a renumbered the dispatch table.)"""
    state = _make_supplied_state()
    state["resolved_risk_profile"] = {
        "profile_id": "future",
        "mode": "supplied",
        "dispatch": "v2_direct",
    }
    with pytest.raises(NotImplementedError, match=r"Got mode='supplied', dispatch='v2_direct'"):
        composer_node(state)


def test_unknown_mode_raises_with_supported_list():
    """An unknown mode → NotImplementedError listing the supported combinations."""
    state = _make_supplied_state()
    state["resolved_risk_profile"] = {
        "profile_id": "future-domestic",
        "mode": "derived_domestic",
        "dispatch": "draps_v1",
    }
    with pytest.raises(NotImplementedError) as exc:
        composer_node(state)
    # The message should name BOTH supported combinations so the operator can fix
    # the profile without re-reading the source.
    msg = str(exc.value)
    assert "derived" in msg
    assert "supplied" in msg
    assert "draps_v1" in msg


def test_missing_validated_inputs_raises():
    """No validated_inputs in state → RuntimeError pointing at wiring bug."""
    state = _make_supplied_state()
    del state["validated_inputs"]
    with pytest.raises(RuntimeError, match="validated_inputs"):
        composer_node(state)


# ───────────────────────────────────────────────────────────────────────
# Direct exercise of the validator helper
# ───────────────────────────────────────────────────────────────────────

def test_validate_supplied_block_accepts_canonical_shape():
    """The validator is a no-op for a clean supplied block (does not raise)."""
    # Should not raise.
    _validate_supplied_block(SAMPLE_SUPPLIED)


def test_validate_supplied_block_rejects_int_value_path_point_ok():
    """ints are acceptable numerics for value (covers `isinstance(.., (int, float))`)."""
    supplied = {
        "sofr_path": [{"time": "2026-02-28T00:00:00", "value": 1}],  # int, not float
        "swap_now_fixed":   0,    # int OK
        "swap_later_fixed": 0.05, # float OK
    }
    # Should not raise.
    _validate_supplied_block(supplied)
