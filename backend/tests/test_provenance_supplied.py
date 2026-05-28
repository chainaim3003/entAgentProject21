"""
test_provenance_supplied.py - Iteration 3 deliverable 5; UPDATED for Iteration 5.

ORIGINAL ROLE (Iter-3)
======================
Pin the minimal supplied-mode contract of N6a Provenance Agent. The Iter-3
contract was "never raises; observation-only stamping of caller-supplied
numerics".

ITERATION-5 UPDATE
==================
The N6a contract changed from "never raises" to "raises on missing source
attribution" per design-v1-iteration-plan.md section 1 ITERATION 5 and
design-v1-detailed-design.md section 1 invariant I7. This file is updated
in-place rather than deleted because each test guards a SEPARATE INVARIANT
that still matters after the contract flipped:

  - Tests 1-7 still pin the supplied-mode stamp shape, count, field paths,
    and audit-log metadata. Count goes from 5 to 9 (5 supplied + 4 loan
    fields - loan fields are now mandatory per the C2 design call). Stamp
    shape changes one field name (request_timestamp -> checksum_or_ts) and
    adds a source_ref key.
  - Tests 8-16 originally pinned "node returns cleanly on weird inputs"
    (never-raises battery). Iter-5 flips the invariant they guard: they
    now pin "node raises ProvenanceInvariantError on weird inputs". Same
    role - pinning the contract at the same boundaries - just with the
    raise direction flipped.
  - Test 17 (composer integration) updates its count assertion.
  - Test 18 (graph wiring smoke) is unchanged.

The new I7-shaped, derived-mode-focused tests live in
test_provenance_invariant.py (Iter-5 deliverable 4). This file remains
supplied-mode-focused.

NO live services required - pure Python. Safe to run in CI.

RUN:
    cd backend
    .venv\\Scripts\\activate
    pytest tests/test_provenance_supplied.py -v
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
sys.path.insert(0, str(BACKEND_DIR))

from provenance import (  # noqa: E402
    SOURCE_TYPE_CALLER_SUPPLIED,
    ProvenanceInvariantError,
    provenance_node,
)


# -----------------------------------------------------------------------------
# Shared fixtures - mirror the composer's knot_payload['supplied'] shape
# AND place validated_inputs at the top level of state (per Iter-5 N6a contract:
# loan fields are read from state.validated_inputs.loan, not from knot_payload).
# -----------------------------------------------------------------------------

SAMPLE_SUPPLIED_BLOCK = {
    "sofr_path": [
        {"time": "2026-02-28T00:00:00", "value": 0.0602},
        {"time": "2026-05-31T00:00:00", "value": 0.0655},
        {"time": "2026-08-31T00:00:00", "value": 0.0704},
    ],
    "swap_now_fixed":   0.0502,
    "swap_later_fixed": 0.0585,
}

SAMPLE_VALIDATED_INPUTS = {
    "loan": {
        "notional_usd": 1_000_000.0,
        "spread_bps":   250.0,
        "term_months":  24,
        "start_date":   "2026-03-01",
        "rate_index":   "SOFR",
    },
    "market": {
        "gtap_commodity_code": "tex",
        "corridor":            {"origin": "India", "destination": "United States"},
        "tariff_assumption_pct": 0.5,
        "rate_curve_index":    "USD-SOFR-FORWARD",
    },
}


def _supplied_state(**overrides) -> dict:
    """Construct a complete supplied-mode state.

    Iter-5: validated_inputs must live at the top level (N6a's _stamp_loan_fields
    reads it from there). knot_payload retains a (legacy) copy as the composer
    would have placed it; the composer itself isn't run here, so the copy is
    purely cosmetic.
    """
    state = {
        "validated_inputs": copy.deepcopy(SAMPLE_VALIDATED_INPUTS),
        "knot_payload": {
            **copy.deepcopy(SAMPLE_VALIDATED_INPUTS),
            "supplied":    copy.deepcopy(SAMPLE_SUPPLIED_BLOCK),
            "_provenance": {"mode": "supplied", "dispatch": "draps_v1"},
        },
        "audit_log": [],
    }
    state.update(overrides)
    return state


def _derived_state_minimal(**overrides) -> dict:
    """Construct a MINIMAL derived-mode state.

    Intentionally missing simulation_result, profile_resolution_path, and the
    hedge_spec_resolver audit entry. Iter-5 N6a's derived branch raises on
    this kind of incomplete state - which is the contract several derived-mode
    tests below pin. For a COMPLETE derived-mode state see derived_state() in
    test_provenance_invariant.py.
    """
    state = {
        "validated_inputs": copy.deepcopy(SAMPLE_VALIDATED_INPUTS),
        "knot_payload": {
            **copy.deepcopy(SAMPLE_VALIDATED_INPUTS),
            "_provenance": {"mode": "derived", "dispatch": "draps_v1"},
        },
        "audit_log": [],
    }
    state.update(overrides)
    return state


# Iter-5 supplied-mode stamp count = 5 supplied (3 SOFR + 2 fixed) + 4 loan = 9.
# Pin the number at module scope so any structural drift surfaces as a single
# failure with a clear message.
_EXPECTED_SUPPLIED_STAMP_COUNT = 9


# =============================================================================
# Supplied-mode: stamps emitted with correct shape and content
# =============================================================================

def test_supplied_emits_stamps_for_every_numeric():
    """Supplied SOFR (3) + supplied fixed rates (2) + loan fields (4) = 9 stamps."""
    result = provenance_node(_supplied_state())
    report = result["provenance_report"]

    assert report["mode"] == "supplied"
    assert len(report["stamps"]) == _EXPECTED_SUPPLIED_STAMP_COUNT


def test_supplied_stamp_shape_has_required_fields():
    """Iter-5 stamp shape: {field, value, source_type, source_ref, checksum_or_ts}.

    All supplied-mode stamps (including loan fields, per the C2 design call)
    carry source_type=caller_supplied.
    """
    result = provenance_node(_supplied_state())
    required = {"field", "value", "source_type", "source_ref", "checksum_or_ts"}
    for stamp in result["provenance_report"]["stamps"]:
        assert set(stamp.keys()) == required
        assert stamp["source_type"] == SOURCE_TYPE_CALLER_SUPPLIED
        assert stamp["source_type"] == "caller_supplied"  # explicit literal pin


def test_supplied_sofr_path_stamps_have_indexed_field_paths():
    """SOFR-path stamps use bracket-indexed field paths matching input order."""
    result = provenance_node(_supplied_state())
    sofr_stamps = [
        s for s in result["provenance_report"]["stamps"]
        if "sofr_path" in s["field"]
    ]

    assert len(sofr_stamps) == 3
    assert sofr_stamps[0]["field"] == "knot_payload.supplied.sofr_path[0].value"
    assert sofr_stamps[1]["field"] == "knot_payload.supplied.sofr_path[1].value"
    assert sofr_stamps[2]["field"] == "knot_payload.supplied.sofr_path[2].value"
    # Values match the input verbatim (no rounding or coercion).
    assert sofr_stamps[0]["value"] == 0.0602
    assert sofr_stamps[1]["value"] == 0.0655
    assert sofr_stamps[2]["value"] == 0.0704


def test_supplied_fixed_rate_stamps_have_dotted_field_paths():
    """Fixed-rate stamps use dotted field paths without bracket indexing."""
    result = provenance_node(_supplied_state())
    rate_stamps = {
        s["field"]: s["value"]
        for s in result["provenance_report"]["stamps"]
        if "fixed" in s["field"] and "loan" not in s["field"]
    }

    assert rate_stamps["knot_payload.supplied.swap_now_fixed"]   == 0.0502
    assert rate_stamps["knot_payload.supplied.swap_later_fixed"] == 0.0585


def test_supplied_checksum_or_ts_is_iso_utc_string():
    """Iter-5 renamed request_timestamp -> checksum_or_ts. For caller_supplied
    stamps this still carries an ISO 8601 UTC timestamp.
    """
    from datetime import datetime

    result = provenance_node(_supplied_state())
    for stamp in result["provenance_report"]["stamps"]:
        parsed = datetime.fromisoformat(stamp["checksum_or_ts"])
        assert parsed.utcoffset() is not None, (
            f"timestamp lacks UTC offset: {stamp['checksum_or_ts']!r}"
        )


def test_supplied_report_has_summary_and_stamped_at():
    """provenance_report carries a human-readable summary + the stamping timestamp."""
    result = provenance_node(_supplied_state())
    report = result["provenance_report"]

    assert "stamped_at" in report
    assert isinstance(report["summary"], str)
    # Iter-5 summary surfaces the total stamp count + the mode.
    assert str(_EXPECTED_SUPPLIED_STAMP_COUNT) in report["summary"]
    assert "I7" in report["summary"]


# -----------------------------------------------------------------------------
# Supplied-mode: audit log
# -----------------------------------------------------------------------------

def test_supplied_audit_log_records_metadata():
    """Audit entry surfaces stamp count + mode + sofr_path_points + fields list."""
    result = provenance_node(_supplied_state())
    entries = result["audit_log"]
    assert len(entries) == 1
    entry = entries[0]

    assert entry["node"] == "provenance"
    out = entry["output"]
    assert out["stamp_count"]      == _EXPECTED_SUPPLIED_STAMP_COUNT
    assert out["mode"]             == "supplied"
    assert out["sofr_path_points"] == 3
    # fields_stamped enumerates every dotted path - supplied + loan together.
    assert len(out["fields_stamped"]) == _EXPECTED_SUPPLIED_STAMP_COUNT
    assert "knot_payload.supplied.swap_now_fixed"      in out["fields_stamped"]
    assert "knot_payload.supplied.swap_later_fixed"    in out["fields_stamped"]
    assert "validated_inputs.loan.notional_usd"        in out["fields_stamped"]
    assert "validated_inputs.loan.start_date"          in out["fields_stamped"]


# =============================================================================
# Derived-mode: contract FLIPPED from "no-op pass-through" to
# "raise on incomplete state per I7"
# =============================================================================

def test_derived_mode_raises_when_simulation_result_missing():
    """Iter-3 returned empty stamps; Iter-5 raises (I7 requires sofr_path)."""
    state = _derived_state_minimal()  # no simulation_result
    with pytest.raises(ProvenanceInvariantError, match="sofr_path"):
        provenance_node(state)


def test_derived_mode_raises_when_state_is_minimal():
    """Iter-3 audited a no-op entry; Iter-5 raises (I7 requires loan + sources)."""
    state = _derived_state_minimal()
    with pytest.raises(ProvenanceInvariantError):
        provenance_node(state)


def test_no_knot_payload_raises():
    """Iter-3 treated this as derived no-op; Iter-5 raises (I7 needs knot_payload)."""
    with pytest.raises(ProvenanceInvariantError, match="knot_payload"):
        provenance_node({})


def test_knot_payload_none_raises():
    """Iter-3 treated as derived no-op; Iter-5 raises."""
    with pytest.raises(ProvenanceInvariantError, match="knot_payload"):
        provenance_node({"knot_payload": None})


# =============================================================================
# Malformed-input boundaries: contract FLIPPED from "skip silently" to
# "raise honestly". Same invariants guarded, opposite assertion direction.
# =============================================================================

def test_supplied_not_a_dict_raises():
    """Iter-3 returned a diagnostic and empty stamps; Iter-5 raises."""
    state = {"knot_payload": {"supplied": "not a dict"}}
    with pytest.raises(ProvenanceInvariantError, match="supplied"):
        provenance_node(state)


def test_non_numeric_sofr_path_value_raises():
    """Iter-3 silently skipped non-numeric SOFR values; Iter-5 raises naming the index."""
    state = _supplied_state()
    state["knot_payload"]["supplied"]["sofr_path"][1]["value"] = "broken"
    with pytest.raises(ProvenanceInvariantError, match=r"sofr_path\[1\]"):
        provenance_node(state)


def test_empty_sofr_path_raises():
    """Iter-3 still stamped fixed rates with empty sofr_path; Iter-5 raises."""
    state = _supplied_state()
    state["knot_payload"]["supplied"]["sofr_path"] = []
    with pytest.raises(ProvenanceInvariantError, match="sofr_path"):
        provenance_node(state)


def test_missing_fixed_rate_raises():
    """Iter-3 silently dropped the missing rate; Iter-5 raises."""
    state = _supplied_state()
    del state["knot_payload"]["supplied"]["swap_later_fixed"]
    with pytest.raises(ProvenanceInvariantError, match="swap_later_fixed"):
        provenance_node(state)


def test_pathological_inputs_all_raise():
    """Cross-cutting: every pathological state SHAPE raises ProvenanceInvariantError.

    Iter-3 asserted this battery returned cleanly with diagnostics. Iter-5 flips
    the invariant: every input here is malformed enough to violate I7, so each
    must raise. The battery itself (same set of pathological inputs) is preserved
    so the boundaries that mattered in Iter-3 still get test coverage.
    """
    pathological_inputs = [
        {},                                               # empty state
        {"knot_payload": None},                           # explicit None
        {"knot_payload": "not even a dict"},              # wrong knot type
        {"knot_payload": {"supplied": "not a dict"}},     # supplied not a dict
        {"knot_payload": {"supplied": []}},               # supplied as list
        {"knot_payload": {"supplied": {"sofr_path": "not a list"}}},  # sofr_path wrong type
        # Note: {"knot_payload": {}} and {"knot_payload": {"supplied": None}} and
        # {"knot_payload": {"supplied": {}}} are derived-mode dispatch paths (no
        # supplied key) - they raise via the derived branch (missing
        # simulation_result + missing validated_inputs.loan). Covered by the
        # derived-mode tests above; not re-tested here.
    ]
    for state in pathological_inputs:
        with pytest.raises(ProvenanceInvariantError):
            provenance_node(state)


# =============================================================================
# Integration: composer output -> provenance_node -> stamps match
# =============================================================================

def test_provenance_stamps_match_composer_output():
    """End-to-end: composer builds knot_payload, provenance stamps its supplied block.

    Proves the contract between composer (producer) and provenance (consumer)
    holds across modules - no key-name drift, no shape divergence.

    Iter-5 update: stamp count is now 9 (5 supplied + 4 loan). The 5 supplied
    stamp values are still pinned verbatim to confirm composer didn't drift.
    """
    from composer import composer_node

    state = {
        "validated_inputs":      copy.deepcopy(SAMPLE_VALIDATED_INPUTS),
        "resolved_risk_profile": {
            "profile_id": "caller_supplied",
            "mode":       "supplied",
            "dispatch":   "draps_v1",
        },
        "resolved_hedge_spec":   {"spec_id": "supplied-rates-example"},
        "supplied":              copy.deepcopy(SAMPLE_SUPPLIED_BLOCK),
        "audit_log":             [],
    }

    composer_result = composer_node(state)
    state["knot_payload"] = composer_result["knot_payload"]

    prov_result = provenance_node(state)
    stamps = prov_result["provenance_report"]["stamps"]

    # 3 supplied path + 2 supplied fixed + 4 loan = 9
    assert len(stamps) == _EXPECTED_SUPPLIED_STAMP_COUNT

    # The 5 supplied-stamp values match the composer-deep-copied supplied block
    # byte-for-byte.
    by_field = {s["field"]: s["value"] for s in stamps}
    assert by_field["knot_payload.supplied.swap_now_fixed"]      == 0.0502
    assert by_field["knot_payload.supplied.swap_later_fixed"]    == 0.0585
    assert by_field["knot_payload.supplied.sofr_path[0].value"]  == 0.0602
    assert by_field["knot_payload.supplied.sofr_path[1].value"]  == 0.0655
    assert by_field["knot_payload.supplied.sofr_path[2].value"]  == 0.0704
    # Loan field values match validated_inputs.loan.
    assert by_field["validated_inputs.loan.notional_usd"] == 1_000_000.0
    assert by_field["validated_inputs.loan.spread_bps"]   == 250.0


# =============================================================================
# Graph wiring smoke: provenance is registered between disclosure and memory
# =============================================================================

def test_graph_builds_with_provenance_node_registered():
    """build_graph() succeeds with the provenance node + edges wired in.

    Cheap insurance that the graph.py wiring did not break the import chain
    or LangGraph's add_node / add_edge calls. A successful build_graph() proves
    that:
      - `from provenance import provenance_node` resolves,
      - g.add_node('provenance', provenance_node) accepted the registration,
      - the new edges (disclosure -> provenance -> memory) reference known nodes.
    The full e14/e15 traversal is exercised by the API-level supplied tests.

    The deeper `.nodes` introspection check has been intentionally avoided here
    because LangGraph's internal StateGraph attribute surface varies across
    versions; the build-success signal is more durable.
    """
    from graph import build_graph

    g = build_graph()
    assert g is not None, "build_graph() returned None - StateGraph not constructed"
