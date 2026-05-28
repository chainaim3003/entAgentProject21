"""
test_provenance_invariant.py - Iteration-5 deliverable 4.

The I7 invariant tests for the FULL Iteration-5 provenance agent.

Pairs with test_provenance_supplied.py (which exercises the Iter-3 supplied
contract, updated in deliverable 3 to match Iter-5's raise-on-missing
behaviour). This file is the *new* test surface for the I7 contract per
design-v1-iteration-plan.md section 1 ITERATION 5 + design-v1-detailed-design.md
section 1 invariant I7.

WHAT THIS FILE PINS
===================
  1. STAMP SHAPE: every stamp has exactly {field, value, source_type,
     source_ref, checksum_or_ts}.
  2. SOURCE-TYPE TAXONOMY: 3 legal values; derived attribution uses
     config_file; loan attribution uses caller_supplied.
  3. DERIVED-MODE STAMP COUNT: N_SOFR + 2 (fixed rates) + 4 (loan fields).
  4. SUPPLIED-MODE STAMP COUNT: N_SOFR + 2 (fixed rates) + 4 (loan fields)
     - same total, but all caller_supplied.
  5. REPORT EXTRAS (derived only): resolved_profile_files lists every
     merged layer with its sha256; resolved_hedge_spec_file similarly.
  6. SHA256 CORRECTNESS: stamps' checksum_or_ts for config_file source
     equals the sha256 of the file on disk.
  7. I7 RAISE-ON-MISSING: any of {missing knot_payload, missing loan
     fields, missing sofr_path, missing fixed rate, empty resolution path,
     missing source file on disk, missing hedge-spec path, malformed
     supplied block} raises ProvenanceInvariantError. Honest failure.
  8. HEDGE-SPEC PATH RECOVERY: works via audit_log OR via hedge_spec_id
     fallback. (Tests the Iter-1-stub bridge.)

NO live services required - pure Python, offline. Uses the real on-disk
config files (india-us-textiles + _default hedge spec) so the sha256
checksum tests actually verify the bytes-on-disk path.

RUN:
    cd backend
    .venv\\Scripts\\activate
    pytest tests/test_provenance_invariant.py -v
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from provenance import (  # noqa: E402
    LEGAL_SOURCE_TYPES,
    SOURCE_TYPE_API,
    SOURCE_TYPE_CALLER_SUPPLIED,
    SOURCE_TYPE_CONFIG_FILE,
    ProvenanceInvariantError,
    provenance_node,
)


# -----------------------------------------------------------------------------
# Canonical file paths under the project root (relative-string form, which is
# the shape profile_resolver writes into state.profile_resolution_path).
# -----------------------------------------------------------------------------

_PROFILE_LEAF_REL   = "config/risk-factor-profiles/export-import/india-us-textiles.json"
_PROFILE_CORRIDOR_REL = "config/risk-factor-profiles/export-import/india-us.json"
_PROFILE_BASE_REL   = "config/risk-factor-profiles/export-import/_base.json"
_HEDGE_SPEC_REL     = "config/hedge-specs/_default.json"


def _sha256_on_disk(rel_path: str) -> str:
    """Compute sha256 of a project-relative file independently of provenance.py.

    Used to cross-check that provenance.py's checksums match the real files.
    Mirrors provenance._sha256_of_file but is intentionally separate so a bug
    in either implementation can't hide behind a shared helper.
    """
    p = REPO_ROOT / rel_path
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# -----------------------------------------------------------------------------
# Shared fixtures - happy-path state for derived and supplied modes.
# Values mirror tests/fixtures/v1-baseline/india-us-textiles.json so derived-mode
# tests use the canonical SOFR path and fixed rates.
# -----------------------------------------------------------------------------

CANONICAL_SOFR_PATH = [
    {"time": "2026-02-28T00:00:00", "value": 0.0602},
    {"time": "2026-05-31T00:00:00", "value": 0.0655},
    {"time": "2026-08-31T00:00:00", "value": 0.0704},
    {"time": "2026-11-30T00:00:00", "value": 0.0747},
    {"time": "2027-02-28T00:00:00", "value": 0.0784},
    {"time": "2027-05-31T00:00:00", "value": 0.0765},
    {"time": "2027-08-31T00:00:00", "value": 0.0733},
    {"time": "2027-11-30T00:00:00", "value": 0.0701},
    {"time": "2028-02-29T00:00:00", "value": 0.0669},
]

CANONICAL_LOAN = {
    "notional_usd": 1_000_000.0,
    "spread_bps":   250.0,
    "term_months":  24,
    "start_date":   "2026-03-01",
    "rate_index":   "SOFR",
}

CANONICAL_MARKET = {
    "gtap_commodity_code":   "tex",
    "corridor":              {"origin": "India", "destination": "United States"},
    "tariff_assumption_pct": 0.5,
    "rate_curve_index":      "USD-SOFR-FORWARD",
}


def _hedge_spec_audit_entry() -> dict:
    """Synthesise an audit_log entry as N3b (hedge_spec_resolver) would emit it.

    The Iter-1 stub records output.source = relative path to the spec file.
    provenance._resolve_hedge_spec_path scans audit_log for this.
    """
    return {
        "node":    "hedge_spec_resolver",
        "summary": "loaded hedge spec default-3-scenario (hardcoded stub)",
        "output": {
            "spec_id":      "default-3-scenario",
            "requested_id": None,
            "source":       _HEDGE_SPEC_REL,
        },
        "ts": "2026-05-27T12:00:00+00:00",
    }


def derived_state() -> dict:
    """Construct a complete derived-mode state for happy-path tests.

    Real on-disk profile + hedge-spec paths so sha256 hashing succeeds.
    Single SOFR path (canonical 9 points) and fixed rates per v1-baseline.
    """
    return {
        "knot_payload": {
            **copy.deepcopy({"loan": CANONICAL_LOAN, "market": CANONICAL_MARKET}),
            "_provenance": {"mode": "derived", "dispatch": "draps_v1"},
        },
        "validated_inputs": {
            "loan":   copy.deepcopy(CANONICAL_LOAN),
            "market": copy.deepcopy(CANONICAL_MARKET),
        },
        "simulation_result": {
            "A_total": 192275.0, "B_total": 150400.0, "C_total": 167390.0,
            "events":  [],
            "sofr_path":             copy.deepcopy(CANONICAL_SOFR_PATH),
            "swap_now_fixed_rate":   0.0502,
            "swap_later_fixed_rate": 0.0585,
        },
        "profile_resolution_path": [
            _PROFILE_LEAF_REL,
            _PROFILE_CORRIDOR_REL,
            _PROFILE_BASE_REL,
        ],
        "hedge_spec_id":  "default-3-scenario",
        "audit_log":      [_hedge_spec_audit_entry()],
    }


def supplied_state() -> dict:
    """Construct a complete supplied-mode state for happy-path tests.

    No profile files - the resolver synthesises a profile in supplied mode,
    so no on-disk attribution. Loan fields still attribute as caller_supplied.
    """
    supplied_block = {
        "sofr_path": [
            {"time": "2026-02-28T00:00:00", "value": 0.0602},
            {"time": "2026-05-31T00:00:00", "value": 0.0655},
            {"time": "2026-08-31T00:00:00", "value": 0.0704},
        ],
        "swap_now_fixed":   0.0502,
        "swap_later_fixed": 0.0585,
    }
    return {
        "knot_payload": {
            **copy.deepcopy({"loan": CANONICAL_LOAN, "market": CANONICAL_MARKET}),
            "supplied":   copy.deepcopy(supplied_block),
            "_provenance": {"mode": "supplied", "dispatch": "draps_v1"},
        },
        "validated_inputs": {
            "loan":   copy.deepcopy(CANONICAL_LOAN),
            "market": copy.deepcopy(CANONICAL_MARKET),
        },
        # supplied mode skips simulation_node (D3 honest-deferral). No
        # simulation_result. N6a's supplied branch must not read it.
        "audit_log": [],  # supplied path doesn't need the hedge_spec audit entry
    }


# =============================================================================
# 1. STAMP SHAPE & SOURCE-TYPE TAXONOMY
# =============================================================================

def test_source_type_constants_form_three_element_set():
    """The 3-element legal source-type set per I7."""
    assert LEGAL_SOURCE_TYPES == {
        SOURCE_TYPE_CONFIG_FILE,
        SOURCE_TYPE_API,
        SOURCE_TYPE_CALLER_SUPPLIED,
    }
    # Pin the string values - downstream code may key on them.
    assert SOURCE_TYPE_CONFIG_FILE     == "config_file"
    assert SOURCE_TYPE_API             == "api"
    assert SOURCE_TYPE_CALLER_SUPPLIED == "caller_supplied"


def test_every_stamp_has_required_keys_derived():
    """Stamp shape exactly {field, value, source_type, source_ref, checksum_or_ts}."""
    result = provenance_node(derived_state())
    required = {"field", "value", "source_type", "source_ref", "checksum_or_ts"}
    for stamp in result["provenance_report"]["stamps"]:
        assert set(stamp.keys()) == required, (
            f"stamp has unexpected keys: {set(stamp.keys()) ^ required}"
        )


def test_every_stamp_has_required_keys_supplied():
    """Same shape contract in supplied mode."""
    result = provenance_node(supplied_state())
    required = {"field", "value", "source_type", "source_ref", "checksum_or_ts"}
    for stamp in result["provenance_report"]["stamps"]:
        assert set(stamp.keys()) == required


def test_every_stamp_source_type_is_legal():
    """No stamp may carry a source_type outside the 3-element legal set."""
    for state in (derived_state(), supplied_state()):
        result = provenance_node(state)
        for stamp in result["provenance_report"]["stamps"]:
            assert stamp["source_type"] in LEGAL_SOURCE_TYPES


# =============================================================================
# 2. DERIVED-MODE HAPPY PATH - counts, types, references
# =============================================================================

def test_derived_stamp_count_is_sofr_plus_two_plus_four_loan():
    """9 SOFR + 2 fixed rates + 4 loan fields = 15 stamps for the canonical run."""
    result = provenance_node(derived_state())
    stamps = result["provenance_report"]["stamps"]
    # 9 SOFR points + 2 fixed rates = 11 derived (config_file) stamps.
    derived_stamps = [s for s in stamps if s["source_type"] == SOURCE_TYPE_CONFIG_FILE]
    loan_stamps    = [s for s in stamps if s["source_type"] == SOURCE_TYPE_CALLER_SUPPLIED]
    assert len(derived_stamps) == 11
    assert len(loan_stamps)    == 4
    assert len(stamps)         == 15


def test_derived_sofr_point_stamps_attribute_to_profile_leaf():
    """Each SOFR-point stamp's source_ref equals the profile leaf path."""
    result = provenance_node(derived_state())
    sofr_stamps = [
        s for s in result["provenance_report"]["stamps"]
        if "simulation_result.sofr_path" in s["field"]
    ]
    assert len(sofr_stamps) == 9
    for s in sofr_stamps:
        assert s["source_type"] == SOURCE_TYPE_CONFIG_FILE
        assert s["source_ref"]  == _PROFILE_LEAF_REL


def test_derived_sofr_point_stamps_carry_leaf_file_sha256():
    """Each SOFR-point stamp's checksum_or_ts equals sha256(leaf file on disk)."""
    expected_sha = _sha256_on_disk(_PROFILE_LEAF_REL)
    result = provenance_node(derived_state())
    sofr_stamps = [
        s for s in result["provenance_report"]["stamps"]
        if "simulation_result.sofr_path" in s["field"]
    ]
    for s in sofr_stamps:
        assert s["checksum_or_ts"] == expected_sha


def test_derived_fixed_rate_stamps_attribute_to_hedge_spec():
    """Each fixed-rate stamp attributes to the hedge-spec file (config_file)."""
    expected_sha = _sha256_on_disk(_HEDGE_SPEC_REL)
    result = provenance_node(derived_state())
    rate_stamps = [
        s for s in result["provenance_report"]["stamps"]
        if "fixed_rate" in s["field"]
    ]
    assert len(rate_stamps) == 2
    fields = {s["field"] for s in rate_stamps}
    assert fields == {
        "simulation_result.swap_now_fixed_rate",
        "simulation_result.swap_later_fixed_rate",
    }
    for s in rate_stamps:
        assert s["source_type"]    == SOURCE_TYPE_CONFIG_FILE
        assert s["source_ref"]     == _HEDGE_SPEC_REL
        assert s["checksum_or_ts"] == expected_sha


def test_derived_sofr_stamp_values_preserved_verbatim():
    """SOFR stamp values match the simulation_result.sofr_path input verbatim."""
    result = provenance_node(derived_state())
    sofr_stamps = [
        s for s in result["provenance_report"]["stamps"]
        if "simulation_result.sofr_path" in s["field"]
    ]
    expected_values = [pt["value"] for pt in CANONICAL_SOFR_PATH]
    actual_values   = [s["value"]  for s in sofr_stamps]
    assert actual_values == expected_values


# =============================================================================
# 3. REPORT EXTRAS - merge chain coverage
# =============================================================================

def test_derived_report_lists_every_resolved_profile_layer():
    """resolved_profile_files has one entry per layer in profile_resolution_path."""
    result = provenance_node(derived_state())
    files = result["provenance_report"]["resolved_profile_files"]
    paths = [f["path"] for f in files]
    assert paths == [_PROFILE_LEAF_REL, _PROFILE_CORRIDOR_REL, _PROFILE_BASE_REL]


def test_derived_report_resolved_profile_files_carry_real_sha256s():
    """Each entry in resolved_profile_files has a sha256 matching on-disk bytes."""
    result = provenance_node(derived_state())
    files = result["provenance_report"]["resolved_profile_files"]
    by_path = {f["path"]: f["sha256"] for f in files}
    assert by_path[_PROFILE_LEAF_REL]     == _sha256_on_disk(_PROFILE_LEAF_REL)
    assert by_path[_PROFILE_CORRIDOR_REL] == _sha256_on_disk(_PROFILE_CORRIDOR_REL)
    assert by_path[_PROFILE_BASE_REL]     == _sha256_on_disk(_PROFILE_BASE_REL)


def test_derived_report_includes_resolved_hedge_spec_file():
    """resolved_hedge_spec_file carries the spec path + sha256."""
    result = provenance_node(derived_state())
    spec = result["provenance_report"]["resolved_hedge_spec_file"]
    assert spec["path"]   == _HEDGE_SPEC_REL
    assert spec["sha256"] == _sha256_on_disk(_HEDGE_SPEC_REL)


def test_supplied_report_omits_profile_files_extras():
    """supplied-mode runs have no config_file extras in the report."""
    result = provenance_node(supplied_state())
    report = result["provenance_report"]
    assert "resolved_profile_files"   not in report
    assert "resolved_hedge_spec_file" not in report


# =============================================================================
# 4. LOAN-FIELD STAMPS - per C2 design: caller_supplied with request_chain ref
# =============================================================================

def test_loan_fields_stamped_as_caller_supplied_in_derived_mode():
    """Loan fields use source_type=caller_supplied even when SOFR is derived."""
    result = provenance_node(derived_state())
    loan_stamps = [
        s for s in result["provenance_report"]["stamps"]
        if s["field"].startswith("validated_inputs.loan.")
    ]
    assert len(loan_stamps) == 4
    for s in loan_stamps:
        assert s["source_type"] == SOURCE_TYPE_CALLER_SUPPLIED


def test_loan_fields_stamped_as_caller_supplied_in_supplied_mode():
    """Loan fields use source_type=caller_supplied in supplied mode too."""
    result = provenance_node(supplied_state())
    loan_stamps = [
        s for s in result["provenance_report"]["stamps"]
        if s["field"].startswith("validated_inputs.loan.")
    ]
    assert len(loan_stamps) == 4
    for s in loan_stamps:
        assert s["source_type"] == SOURCE_TYPE_CALLER_SUPPLIED


def test_loan_field_source_ref_records_request_chain():
    """source_ref for loan fields records 'request body -> validated_inputs.X'."""
    result = provenance_node(derived_state())
    loan_stamps = [
        s for s in result["provenance_report"]["stamps"]
        if s["field"].startswith("validated_inputs.loan.")
    ]
    for s in loan_stamps:
        # field == 'validated_inputs.loan.notional_usd'
        # source_ref ends with the same suffix
        suffix = s["field"].split(".")[-1]
        assert "private_loan_doc" in s["source_ref"]
        assert s["source_ref"].endswith(f"validated_inputs.loan.{suffix}")


def test_loan_field_checksum_or_ts_is_iso_utc_timestamp():
    """Loan-field stamps carry an ISO 8601 UTC timestamp in checksum_or_ts."""
    result = provenance_node(derived_state())
    loan_stamps = [
        s for s in result["provenance_report"]["stamps"]
        if s["field"].startswith("validated_inputs.loan.")
    ]
    for s in loan_stamps:
        # Should parse cleanly and carry a UTC offset.
        parsed = datetime.fromisoformat(s["checksum_or_ts"])
        assert parsed.utcoffset() is not None


def test_loan_fields_stamped_in_canonical_order():
    """Loan stamps appear in (notional_usd, spread_bps, term_months, start_date) order."""
    result = provenance_node(derived_state())
    loan_fields = [
        s["field"] for s in result["provenance_report"]["stamps"]
        if s["field"].startswith("validated_inputs.loan.")
    ]
    assert loan_fields == [
        "validated_inputs.loan.notional_usd",
        "validated_inputs.loan.spread_bps",
        "validated_inputs.loan.term_months",
        "validated_inputs.loan.start_date",
    ]


# =============================================================================
# 5. SUPPLIED-MODE HAPPY PATH - counts + source-types
# =============================================================================

def test_supplied_stamp_count_is_sofr_plus_two_plus_four_loan():
    """3 supplied SOFR + 2 supplied fixed + 4 loan = 9 stamps."""
    result = provenance_node(supplied_state())
    stamps = result["provenance_report"]["stamps"]
    assert len(stamps) == 3 + 2 + 4


def test_supplied_all_stamps_are_caller_supplied():
    """In supplied mode every stamp is caller_supplied (no config_file)."""
    result = provenance_node(supplied_state())
    for s in result["provenance_report"]["stamps"]:
        assert s["source_type"] == SOURCE_TYPE_CALLER_SUPPLIED


def test_supplied_sofr_stamps_point_at_request_body_field():
    """Supplied SOFR stamps' source_ref names the request-body field they came from."""
    result = provenance_node(supplied_state())
    sofr_stamps = [
        s for s in result["provenance_report"]["stamps"]
        if s["field"].startswith("knot_payload.supplied.sofr_path")
    ]
    assert len(sofr_stamps) == 3
    for i, s in enumerate(sofr_stamps):
        assert s["source_ref"] == f"request.body.supplied.sofr_path[{i}].value"


def test_supplied_fixed_rate_stamps_point_at_request_body_fields():
    """Supplied fixed-rate stamps' source_ref names the request-body field."""
    result = provenance_node(supplied_state())
    by_field = {
        s["field"]: s["source_ref"]
        for s in result["provenance_report"]["stamps"]
        if "swap_" in s["field"] and "fixed" in s["field"]
    }
    assert by_field["knot_payload.supplied.swap_now_fixed"]   == "request.body.supplied.swap_now_fixed"
    assert by_field["knot_payload.supplied.swap_later_fixed"] == "request.body.supplied.swap_later_fixed"


# =============================================================================
# 6. HEDGE-SPEC PATH RECOVERY
# =============================================================================

def test_hedge_spec_path_recovered_from_audit_log():
    """N6a finds spec path in audit_log[?node=='hedge_spec_resolver'].output.source.

    This is the SOLE recovery path. The earlier sketch of N6a also tried a
    `state.hedge_spec_id`-derived fallback, but `hedge_spec_id` is the spec_id
    FIELD INSIDE the JSON (e.g. 'default-3-scenario'), not the filename
    (`_default.json`), so the mapping is not 1:1. The Iter-1 stub always emits
    the audit_log entry, so real runs never need a fallback.
    """
    state = derived_state()
    # No hedge_spec_id at all - audit_log alone must satisfy recovery.
    state.pop("hedge_spec_id", None)
    result = provenance_node(state)
    spec = result["provenance_report"]["resolved_hedge_spec_file"]
    assert spec["path"] == _HEDGE_SPEC_REL


def test_hedge_spec_path_unrecoverable_without_audit_log():
    """Without the hedge_spec_resolver audit entry, N6a raises (no fallback).

    Pins the removal of the spec-id-as-filename fallback. Real runs always
    traverse N3b and emit the audit entry; tests must include it too.
    """
    state = derived_state()
    state["audit_log"] = []
    state["hedge_spec_id"] = "default-3-scenario"  # ignored: not a filename
    with pytest.raises(ProvenanceInvariantError, match="hedge-spec"):
        provenance_node(state)


# =============================================================================
# 7. I7 RAISE-ON-MISSING - the core I7 enforcement
# =============================================================================

def test_raises_when_knot_payload_missing():
    """No knot_payload in state - I7 violation, raises."""
    with pytest.raises(ProvenanceInvariantError, match="knot_payload"):
        provenance_node({})


def test_raises_when_knot_payload_is_none():
    """knot_payload=None - I7 violation, raises (Iter-3 silently passed)."""
    with pytest.raises(ProvenanceInvariantError, match="knot_payload"):
        provenance_node({"knot_payload": None})


def test_raises_when_knot_payload_not_a_dict():
    """knot_payload is a list/string - I7 violation, raises."""
    with pytest.raises(ProvenanceInvariantError, match="knot_payload"):
        provenance_node({"knot_payload": "not a dict"})


def test_raises_when_validated_inputs_loan_missing_derived():
    """validated_inputs.loan absent in derived mode - cannot stamp loan fields."""
    state = derived_state()
    state["validated_inputs"] = {}  # loan missing
    with pytest.raises(ProvenanceInvariantError, match="validated_inputs.loan"):
        provenance_node(state)


def test_raises_when_validated_inputs_loan_missing_supplied():
    """validated_inputs.loan absent in supplied mode - cannot stamp loan fields."""
    state = supplied_state()
    state["validated_inputs"] = {}
    with pytest.raises(ProvenanceInvariantError, match="validated_inputs.loan"):
        provenance_node(state)


def test_raises_when_a_required_loan_field_is_missing():
    """A single loan field absent - I7 names the missing field(s)."""
    state = derived_state()
    del state["validated_inputs"]["loan"]["notional_usd"]
    with pytest.raises(ProvenanceInvariantError, match="notional_usd"):
        provenance_node(state)


def test_raises_when_loan_field_is_blank_string():
    """Empty start_date string - treated as missing per spec, raises."""
    state = derived_state()
    state["validated_inputs"]["loan"]["start_date"] = "   "
    with pytest.raises(ProvenanceInvariantError, match="start_date"):
        provenance_node(state)


def test_raises_when_simulation_result_sofr_path_missing_derived():
    """No sofr_path on simulation_result - DRAPS shape drift, raises honestly."""
    state = derived_state()
    state["simulation_result"]["sofr_path"] = None
    with pytest.raises(ProvenanceInvariantError, match="sofr_path"):
        provenance_node(state)


def test_raises_when_simulation_result_sofr_path_empty():
    """Empty sofr_path list - I7 violation (no points to attribute)."""
    state = derived_state()
    state["simulation_result"]["sofr_path"] = []
    with pytest.raises(ProvenanceInvariantError, match="sofr_path"):
        provenance_node(state)


def test_raises_when_swap_now_fixed_rate_non_numeric():
    """Non-numeric swap_now_fixed_rate - cannot attribute."""
    state = derived_state()
    state["simulation_result"]["swap_now_fixed_rate"] = "not a number"
    with pytest.raises(ProvenanceInvariantError, match="swap_now_fixed_rate"):
        provenance_node(state)


def test_raises_when_swap_later_fixed_rate_is_none():
    """swap_later_fixed_rate=None - cannot attribute."""
    state = derived_state()
    state["simulation_result"]["swap_later_fixed_rate"] = None
    with pytest.raises(ProvenanceInvariantError, match="swap_later_fixed_rate"):
        provenance_node(state)


def test_raises_when_profile_resolution_path_empty():
    """Empty profile_resolution_path - cannot attribute SOFR to a file."""
    state = derived_state()
    state["profile_resolution_path"] = []
    with pytest.raises(ProvenanceInvariantError, match="profile_resolution_path"):
        provenance_node(state)


def test_raises_when_profile_leaf_file_does_not_exist():
    """Resolution_path entry points at a non-existent file - sha256 fails honestly."""
    state = derived_state()
    state["profile_resolution_path"] = ["config/risk-factor-profiles/export-import/does-not-exist.json"]
    with pytest.raises(ProvenanceInvariantError, match="sha256"):
        provenance_node(state)


def test_raises_when_hedge_spec_path_unrecoverable():
    """No hedge_spec_resolver entry in audit_log - cannot attribute, raises."""
    state = derived_state()
    state["audit_log"] = []
    state.pop("hedge_spec_id", None)
    with pytest.raises(ProvenanceInvariantError, match="hedge-spec"):
        provenance_node(state)


def test_raises_when_hedge_spec_audit_entry_points_at_nonexistent_file():
    """audit_log entry names a missing file - sha256 raises honestly."""
    state = derived_state()
    bad_entry = copy.deepcopy(_hedge_spec_audit_entry())
    bad_entry["output"]["source"] = "config/hedge-specs/does-not-exist.json"
    state["audit_log"] = [bad_entry]
    with pytest.raises(ProvenanceInvariantError, match="sha256"):
        provenance_node(state)


def test_raises_when_supplied_block_is_not_a_dict():
    """knot_payload.supplied is a string - I7 violation in supplied path."""
    state = supplied_state()
    state["knot_payload"]["supplied"] = "not a dict"
    with pytest.raises(ProvenanceInvariantError, match="supplied"):
        provenance_node(state)


def test_raises_when_supplied_sofr_path_empty():
    """Empty supplied.sofr_path - I7 violation."""
    state = supplied_state()
    state["knot_payload"]["supplied"]["sofr_path"] = []
    with pytest.raises(ProvenanceInvariantError, match="sofr_path"):
        provenance_node(state)


def test_raises_when_supplied_sofr_point_value_non_numeric():
    """A supplied SOFR point with a string value - raises naming the index."""
    state = supplied_state()
    state["knot_payload"]["supplied"]["sofr_path"][1]["value"] = "broken"
    with pytest.raises(ProvenanceInvariantError, match=r"sofr_path\[1\]"):
        provenance_node(state)


def test_raises_when_supplied_sofr_point_value_is_bool():
    """A supplied SOFR point with value=True (bool is int subclass) - raises."""
    state = supplied_state()
    state["knot_payload"]["supplied"]["sofr_path"][0]["value"] = True
    with pytest.raises(ProvenanceInvariantError, match=r"sofr_path\[0\]"):
        provenance_node(state)


def test_raises_when_supplied_swap_now_fixed_missing():
    """supplied.swap_now_fixed absent - I7 violation."""
    state = supplied_state()
    del state["knot_payload"]["supplied"]["swap_now_fixed"]
    with pytest.raises(ProvenanceInvariantError, match="swap_now_fixed"):
        provenance_node(state)


def test_raises_when_supplied_swap_later_fixed_non_numeric():
    """supplied.swap_later_fixed=string - I7 violation."""
    state = supplied_state()
    state["knot_payload"]["supplied"]["swap_later_fixed"] = "broken"
    with pytest.raises(ProvenanceInvariantError, match="swap_later_fixed"):
        provenance_node(state)


def test_raise_exception_is_provenance_invariant_error():
    """Confirms the exception class is ProvenanceInvariantError, not RuntimeError directly.

    Subclass relationship is allowed (and tested above via isinstance match in
    pytest.raises). This test pins that the exception is the named class so
    callers can `except ProvenanceInvariantError` precisely.
    """
    try:
        provenance_node({})
    except ProvenanceInvariantError as e:
        # The named class IS the exception type, not just a base.
        assert type(e).__name__ == "ProvenanceInvariantError"
        return
    pytest.fail("expected ProvenanceInvariantError")


def test_provenance_invariant_error_is_runtime_error_subclass():
    """ProvenanceInvariantError extends RuntimeError so generic handlers still catch it."""
    assert issubclass(ProvenanceInvariantError, RuntimeError)


# =============================================================================
# 8. INTEGRATION - composer output flows into provenance_node
# =============================================================================

def test_composer_then_provenance_supplied_end_to_end():
    """Build state, run composer, run provenance - shape matches end-to-end."""
    from composer import composer_node  # local import keeps imports cheap

    supplied_block = {
        "sofr_path": [
            {"time": "2026-02-28T00:00:00", "value": 0.0602},
            {"time": "2026-05-31T00:00:00", "value": 0.0655},
            {"time": "2026-08-31T00:00:00", "value": 0.0704},
        ],
        "swap_now_fixed":   0.0502,
        "swap_later_fixed": 0.0585,
    }
    state = {
        "validated_inputs":      {"loan": copy.deepcopy(CANONICAL_LOAN),
                                  "market": copy.deepcopy(CANONICAL_MARKET)},
        "resolved_risk_profile": {
            "profile_id":    "caller_supplied",
            "mode":          "supplied",
            "dispatch":      "draps_v1",
            "hedge_spec_id": "supplied-rates-example",
        },
        "resolved_hedge_spec":   {"spec_id": "supplied-rates-example"},
        "supplied":              copy.deepcopy(supplied_block),
        "audit_log":             [],
    }

    composer_result = composer_node(state)
    state["knot_payload"] = composer_result["knot_payload"]

    result = provenance_node(state)
    stamps = result["provenance_report"]["stamps"]

    # 3 supplied SOFR + 2 supplied fixed + 4 loan = 9
    assert len(stamps) == 9
    assert all(s["source_type"] == SOURCE_TYPE_CALLER_SUPPLIED for s in stamps)


# =============================================================================
# 9. AUDIT-LOG ENTRY - the run summary
# =============================================================================

def test_derived_audit_log_records_satisfied_i7():
    """Audit entry for derived run records stamp_count + mode + leaf + spec."""
    result = provenance_node(derived_state())
    entries = result["audit_log"]
    assert len(entries) == 1
    out = entries[0]["output"]
    assert out["mode"]                    == "derived"
    assert out["stamp_count"]             == 15
    assert out["sofr_path_points"]        == 9
    assert out["resolved_profile_layers"] == 3
    assert out["profile_leaf"]            == _PROFILE_LEAF_REL
    assert out["hedge_spec"]              == _HEDGE_SPEC_REL


def test_supplied_audit_log_records_satisfied_i7():
    """Audit entry for supplied run records stamp_count + mode + fields list."""
    result = provenance_node(supplied_state())
    entries = result["audit_log"]
    assert len(entries) == 1
    out = entries[0]["output"]
    assert out["mode"]             == "supplied"
    assert out["stamp_count"]      == 9
    assert out["sofr_path_points"] == 3
    assert len(out["fields_stamped"]) == 9
