"""
test_draps_client_extract.py - Iteration-5 deliverable 1.

Offline unit tests for the SOFR-path + fixed-rate extractors added to
draps_client.py in Iteration 5, plus the extended _extract_scenarios contract.

WHY THIS FILE EXISTS
====================
draps_client.run_simulation used to drop SOFR_PATH and the two SWAP fixed
rates on the floor - only A/B/C totals + events were carried through. The
N6a Provenance Agent (Iter-5) needs them to enumerate per-point provenance
attributions, so draps_client now surfaces them.

test_byte_equality_v1.py validates the same parsing live against DRAPS, but
that test requires DRAPS + ACTUS running. This file pins the extractor
contract offline (no live services), so byte-equality's role can stay
focused on byte-equality.

WHAT IT ASSERTS
===============
  - _extract_sofr_path_from_env: parses real-shape input, returns None on every
    plausible malformation. Never raises.
  - _extract_fixed_rate_from_payload: walks the SWAPS contractStructure to find
    the fixed-leg nominalInterestRate, returns None on every plausible
    malformation. Never raises.
  - _extract_scenarios path-0 (env-vars happy path): all 7 fields populated;
    sofr_path / fixed rates equal the values parsed from env_vars.
  - _extract_scenarios path-0 with no SOFR_PATH / no SWAP payloads: A/B/C +
    events still populated; the 3 new fields are None (downstream N6a will
    then raise per I7).
  - _extract_scenarios fallback paths 1/2/3: the 3 new fields are None.

NO LIVE SERVICES required - pure Python. Safe to run in CI.

RUN:
    cd backend
    .venv\\Scripts\\activate
    pytest tests/test_draps_client_extract.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
sys.path.insert(0, str(BACKEND_DIR))

from draps_client import (  # noqa: E402
    _extract_fixed_rate_from_payload,
    _extract_scenarios,
    _extract_sofr_path_from_env,
)


# -----------------------------------------------------------------------------
# Real-shape fixtures - mirror the DRAPS environmentVariables payload that
# test_byte_equality_v1.py reads live. Values borrowed from the v1-baseline
# fixture (tests/fixtures/v1-baseline/india-us-textiles.json) so any drift in
# the canonical SOFR path can be cross-checked.
# -----------------------------------------------------------------------------

SOFR_PATH_STR = json.dumps([
    {"time": "2026-02-28T00:00:00", "value": 0.0602},
    {"time": "2026-05-31T00:00:00", "value": 0.0655},
    {"time": "2026-08-31T00:00:00", "value": 0.0704},
])


def _swap_payload(fixed_id: str, fixed_rate: float) -> str:
    """Build a JSON string mirroring DRAPS's SWAP_NOW_PAYLOAD / SWAP_LATER_PAYLOAD shape.

    Realistic enough to exercise the contractStructure walk: two contracts
    (one PAM for the loan, one SWAPS with two structure entries - fixed leg
    and float leg). The extractor must find the fixed leg by contractID.
    """
    return json.dumps({
        "contracts": [
            {"contractType": "PAM", "contractID": "LOAN-1"},
            {
                "contractType": "SWAPS",
                "contractID":   "SWAP-1",
                "contractStructure": [
                    {"object": {"contractID": fixed_id,         "nominalInterestRate": fixed_rate}},
                    {"object": {"contractID": "SWAP-FLOAT-LEG", "nominalInterestRate": 0.0}},
                ],
            },
        ],
    })


def _draps_response(
    *,
    a: str = "192275.0",
    b: str = "150400.0",
    c: str = "167390.0",
    sofr_path: str | None = SOFR_PATH_STR,
    swap_now: str | None = None,
    swap_later: str | None = None,
    extra_env: dict | None = None,
) -> dict:
    """Build a synthetic DRAPS response with shape == path-0 (env-vars happy path).

    Totals arrive as strings per DRAPS's pm.environment.set(String(value))
    convention. Optional fields are omitted when None so each can be exercised
    independently.
    """
    env: dict = {"A_total": a, "B_total": b, "C_total": c}
    if sofr_path is not None:
        env["SOFR_PATH"] = sofr_path
    if swap_now is not None:
        env["SWAP_NOW_PAYLOAD"] = swap_now
    if swap_later is not None:
        env["SWAP_LATER_PAYLOAD"] = swap_later
    if extra_env:
        env.update(extra_env)
    return {"environmentVariables": env}


# =============================================================================
# _extract_sofr_path_from_env
# =============================================================================

def test_sofr_path_extracts_real_shape():
    """Real-shape SOFR_PATH string parses into the expected list of dicts."""
    result = _extract_sofr_path_from_env({"SOFR_PATH": SOFR_PATH_STR})
    assert result is not None
    assert len(result) == 3
    assert result[0] == {"time": "2026-02-28T00:00:00", "value": 0.0602}
    assert result[1] == {"time": "2026-05-31T00:00:00", "value": 0.0655}
    assert result[2] == {"time": "2026-08-31T00:00:00", "value": 0.0704}


def test_sofr_path_missing_returns_none():
    """No SOFR_PATH key in env_vars -> None, no raise."""
    assert _extract_sofr_path_from_env({}) is None


def test_sofr_path_none_returns_none():
    """SOFR_PATH explicitly None -> None."""
    assert _extract_sofr_path_from_env({"SOFR_PATH": None}) is None


def test_sofr_path_empty_string_returns_none():
    """Empty string -> None (not 'parsed as empty list')."""
    assert _extract_sofr_path_from_env({"SOFR_PATH": ""}) is None
    assert _extract_sofr_path_from_env({"SOFR_PATH": "   "}) is None


def test_sofr_path_invalid_json_returns_none():
    """Malformed JSON -> None (catches JSONDecodeError silently)."""
    assert _extract_sofr_path_from_env({"SOFR_PATH": "not json {{{"}) is None


def test_sofr_path_not_a_list_returns_none():
    """JSON object (not a list) -> None."""
    assert _extract_sofr_path_from_env({"SOFR_PATH": '{"foo": "bar"}'}) is None


def test_sofr_path_empty_list_returns_none():
    """Empty list -> None (no points to attribute = no path)."""
    assert _extract_sofr_path_from_env({"SOFR_PATH": "[]"}) is None


def test_sofr_path_point_missing_value_returns_none():
    """Any point missing 'value' invalidates the whole path."""
    bad = json.dumps([{"time": "2026-02-28T00:00:00"}])
    assert _extract_sofr_path_from_env({"SOFR_PATH": bad}) is None


def test_sofr_path_point_missing_time_returns_none():
    """Any point missing 'time' invalidates the whole path."""
    bad = json.dumps([{"value": 0.06}])
    assert _extract_sofr_path_from_env({"SOFR_PATH": bad}) is None


def test_sofr_path_non_numeric_value_returns_none():
    """A point with a string 'value' invalidates the whole path."""
    bad = json.dumps([{"time": "2026-02-28T00:00:00", "value": "broken"}])
    assert _extract_sofr_path_from_env({"SOFR_PATH": bad}) is None


def test_sofr_path_boolean_value_returns_none():
    """A point with a boolean 'value' invalidates the path (bool is int subclass)."""
    bad = json.dumps([{"time": "2026-02-28T00:00:00", "value": True}])
    assert _extract_sofr_path_from_env({"SOFR_PATH": bad}) is None


def test_sofr_path_non_dict_point_returns_none():
    """A list element that isn't a dict invalidates the path."""
    bad = json.dumps(["not a dict"])
    assert _extract_sofr_path_from_env({"SOFR_PATH": bad}) is None


# =============================================================================
# _extract_fixed_rate_from_payload
# =============================================================================

def test_fixed_rate_extracts_swap_b_fixed():
    """Real-shape SWAP_NOW_PAYLOAD: SWAP-B-FIXED nominalInterestRate = 0.0502."""
    payload = _swap_payload("SWAP-B-FIXED", 0.0502)
    assert _extract_fixed_rate_from_payload(payload, "SWAP-B-FIXED") == 0.0502


def test_fixed_rate_extracts_swap_c_fixed():
    """Real-shape SWAP_LATER_PAYLOAD: SWAP-C-FIXED nominalInterestRate = 0.0585."""
    payload = _swap_payload("SWAP-C-FIXED", 0.0585)
    assert _extract_fixed_rate_from_payload(payload, "SWAP-C-FIXED") == 0.0585


def test_fixed_rate_missing_contract_id_returns_none():
    """Payload exists but no contract has the requested ID -> None."""
    payload = _swap_payload("SOME-OTHER-ID", 0.05)
    assert _extract_fixed_rate_from_payload(payload, "SWAP-B-FIXED") is None


def test_fixed_rate_none_payload_returns_none():
    """payload=None -> None, no raise."""
    assert _extract_fixed_rate_from_payload(None, "SWAP-B-FIXED") is None


def test_fixed_rate_non_string_payload_returns_none():
    """payload=dict (not a string) -> None. The contract is STRING-encoded JSON."""
    assert _extract_fixed_rate_from_payload({"contracts": []}, "SWAP-B-FIXED") is None


def test_fixed_rate_invalid_json_returns_none():
    """Malformed JSON -> None."""
    assert _extract_fixed_rate_from_payload("not json {", "SWAP-B-FIXED") is None


def test_fixed_rate_no_swaps_contract_returns_none():
    """Payload has contracts but none are SWAPS -> None."""
    payload = json.dumps({"contracts": [{"contractType": "PAM", "contractID": "LOAN-1"}]})
    assert _extract_fixed_rate_from_payload(payload, "SWAP-B-FIXED") is None


def test_fixed_rate_string_numeric_coerced():
    """A nominalInterestRate stored as a string number is coerced to float."""
    payload = json.dumps({
        "contracts": [{
            "contractType": "SWAPS",
            "contractStructure": [
                {"object": {"contractID": "SWAP-B-FIXED", "nominalInterestRate": "0.0502"}},
            ],
        }],
    })
    assert _extract_fixed_rate_from_payload(payload, "SWAP-B-FIXED") == 0.0502


def test_fixed_rate_unparseable_string_returns_none():
    """A nominalInterestRate that's a non-numeric string -> None."""
    payload = json.dumps({
        "contracts": [{
            "contractType": "SWAPS",
            "contractStructure": [
                {"object": {"contractID": "SWAP-B-FIXED", "nominalInterestRate": "abc"}},
            ],
        }],
    })
    assert _extract_fixed_rate_from_payload(payload, "SWAP-B-FIXED") is None


def test_fixed_rate_boolean_rate_returns_none():
    """A nominalInterestRate=True (bool) -> None (bool is int subclass, must reject)."""
    payload = json.dumps({
        "contracts": [{
            "contractType": "SWAPS",
            "contractStructure": [
                {"object": {"contractID": "SWAP-B-FIXED", "nominalInterestRate": True}},
            ],
        }],
    })
    assert _extract_fixed_rate_from_payload(payload, "SWAP-B-FIXED") is None


# =============================================================================
# _extract_scenarios: extended path-0 contract
# =============================================================================

def test_extract_scenarios_happy_path_populates_all_fields():
    """env-vars happy path: A/B/C + events + sofr_path + 2 fixed rates all populated."""
    response = _draps_response(
        swap_now=_swap_payload("SWAP-B-FIXED", 0.0502),
        swap_later=_swap_payload("SWAP-C-FIXED", 0.0585),
    )
    result = _extract_scenarios(response)

    # Pre-Iter-5 fields still present, same values
    assert result["A_total"] == 192275.0
    assert result["B_total"] == 150400.0
    assert result["C_total"] == 167390.0
    assert result["events"] == []  # no `simulation` in this synthetic response

    # Iter-5 additions
    assert result["sofr_path"] is not None
    assert len(result["sofr_path"]) == 3
    assert result["sofr_path"][0]["value"] == 0.0602
    assert result["swap_now_fixed_rate"] == 0.0502
    assert result["swap_later_fixed_rate"] == 0.0585


def test_extract_scenarios_path0_without_sofr_returns_none_for_sofr_only():
    """env-vars path with no SOFR_PATH: A/B/C populated; sofr_path is None."""
    response = _draps_response(sofr_path=None)
    result = _extract_scenarios(response)

    assert result["A_total"] == 192275.0  # base fields unchanged
    assert result["sofr_path"] is None
    assert result["swap_now_fixed_rate"] is None
    assert result["swap_later_fixed_rate"] is None


def test_extract_scenarios_path0_without_swap_payloads():
    """env-vars path with SOFR but no SWAP payloads: sofr_path populated, rates None."""
    response = _draps_response()  # SOFR_PATH set, SWAP payloads not set
    result = _extract_scenarios(response)

    assert result["sofr_path"] is not None
    assert result["swap_now_fixed_rate"] is None
    assert result["swap_later_fixed_rate"] is None


def test_extract_scenarios_path0_with_malformed_sofr():
    """env-vars path with malformed SOFR_PATH: sofr_path is None, others unaffected."""
    response = _draps_response(sofr_path="not json {")
    result = _extract_scenarios(response)

    assert result["A_total"] == 192275.0
    assert result["sofr_path"] is None


# =============================================================================
# _extract_scenarios: fallback paths 1/2/3 carry the new fields as None
# =============================================================================

def test_extract_scenarios_path1_flat_shape_has_none_new_fields():
    """Flat top-level A/B/C - the 3 new fields default to None (per I7)."""
    response = {"A_total": 100.0, "B_total": 90.0, "C_total": 95.0}
    result = _extract_scenarios(response)

    assert result["A_total"] == 100.0
    assert result["sofr_path"] is None
    assert result["swap_now_fixed_rate"] is None
    assert result["swap_later_fixed_rate"] is None


def test_extract_scenarios_path2_scenarios_shape_has_none_new_fields():
    """Nested 'scenarios' shape - the 3 new fields default to None."""
    response = {
        "scenarios": {
            "A": {"total": 100.0},
            "B": {"total": 90.0},
            "C": {"total": 95.0},
        },
    }
    result = _extract_scenarios(response)

    assert result["A_total"] == 100.0
    assert result["sofr_path"] is None
    assert result["swap_now_fixed_rate"] is None
    assert result["swap_later_fixed_rate"] is None


def test_extract_scenarios_path3_result_shape_has_none_new_fields():
    """Nested 'result' shape - the 3 new fields default to None."""
    response = {
        "result": {"A_total": 100.0, "B_total": 90.0, "C_total": 95.0},
    }
    result = _extract_scenarios(response)

    assert result["A_total"] == 100.0
    assert result["sofr_path"] is None
    assert result["swap_now_fixed_rate"] is None
    assert result["swap_later_fixed_rate"] is None


def test_extract_scenarios_unrecognized_shape_still_raises():
    """A response with no recognised shape still raises (honest failure preserved)."""
    with pytest.raises(RuntimeError, match="unexpected"):
        _extract_scenarios({"totally": "unknown shape"})


def test_extract_scenarios_non_dict_raises():
    """Non-dict input still raises (precondition preserved)."""
    with pytest.raises(RuntimeError, match="non-object"):
        _extract_scenarios(["not", "a", "dict"])  # type: ignore[arg-type]
