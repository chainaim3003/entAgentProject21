"""
test_api_supplied.py — Iteration 3 deliverable 4a.

Unit-tests the POST /run body extension for supplied mode:
  • Pydantic validation of the new Supplied / SuppliedSofrPathPoint models
  • RunRequest now accepts an optional `supplied` field
  • _build_initial_state lifts supplied into state['supplied'] when present,
    omits it otherwise (V1 baseline shape preserved)
  • The model_dump() output matches the composer's expected shape — verified
    by feeding it through composer._validate_supplied_block directly. This is
    the cross-module contract: API edge ↔ graph boundary.

No FastAPI stack required — _build_initial_state is extracted from the route
handler precisely so it can be unit-tested in isolation. The full
end-to-end API integration test (TestClient + graph) is deferred to a later
iteration once the simulation/DRAPS bridge is wired.

RUN:
    cd backend
    .venv\\Scripts\\activate
    pytest tests/test_api_supplied.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
sys.path.insert(0, str(BACKEND_DIR))

from api import RunRequest, Supplied, SuppliedSofrPathPoint, _build_initial_state  # noqa: E402
from composer import _validate_supplied_block  # noqa: E402


# ───────────────────────────────────────────────────────────────────────
# Sample data
# ───────────────────────────────────────────────────────────────────────

VALID_SUPPLIED_BODY = {
    "sofr_path": [
        {"time": "2026-02-28T00:00:00", "value": 0.0602},
        {"time": "2026-05-31T00:00:00", "value": 0.0655},
        {"time": "2026-08-31T00:00:00", "value": 0.0704},
    ],
    "swap_now_fixed":   0.0502,
    "swap_later_fixed": 0.0585,
}

V1_BODY = {
    "prompt": "Should I hedge my $1M India-US textile loan with a swap now or wait 3 months?",
    "loan_doc": "Loan agreement text here...",
}

SUPPLIED_BODY = {**V1_BODY, "supplied": VALID_SUPPLIED_BODY}


# ───────────────────────────────────────────────────────────────────────
# RunRequest schema acceptance
# ───────────────────────────────────────────────────────────────────────

def test_run_request_v1_shape_still_valid():
    """V1 shape (no 'supplied') still parses cleanly and yields supplied=None."""
    req = RunRequest(**V1_BODY)
    assert req.supplied is None
    assert req.prompt == V1_BODY["prompt"]
    assert req.loan_doc == V1_BODY["loan_doc"]


def test_run_request_accepts_supplied_block():
    """Supplied block parses into a typed Pydantic model."""
    req = RunRequest(**SUPPLIED_BODY)
    assert req.supplied is not None
    assert isinstance(req.supplied, Supplied)
    assert len(req.supplied.sofr_path) == 3
    assert req.supplied.swap_now_fixed   == 0.0502
    assert req.supplied.swap_later_fixed == 0.0585
    # Each path point is a typed model.
    assert isinstance(req.supplied.sofr_path[0], SuppliedSofrPathPoint)
    assert req.supplied.sofr_path[0].time == "2026-02-28T00:00:00"
    assert req.supplied.sofr_path[0].value == 0.0602


# ───────────────────────────────────────────────────────────────────────
# Pydantic validation — honest rejection at the API edge
# ───────────────────────────────────────────────────────────────────────

def test_supplied_rejects_empty_sofr_path():
    """min_length=1 on sofr_path rejects empty list at the API edge."""
    bad = {**SUPPLIED_BODY, "supplied": {**VALID_SUPPLIED_BODY, "sofr_path": []}}
    with pytest.raises(ValidationError) as exc:
        RunRequest(**bad)
    # The error should reference sofr_path.
    assert "sofr_path" in str(exc.value)


def test_supplied_rejects_sofr_path_point_missing_value():
    """A path point missing 'value' is rejected by Pydantic."""
    bad_path = [{"time": "2026-02-28T00:00:00"}]  # value missing
    bad = {**SUPPLIED_BODY, "supplied": {**VALID_SUPPLIED_BODY, "sofr_path": bad_path}}
    with pytest.raises(ValidationError) as exc:
        RunRequest(**bad)
    assert "value" in str(exc.value).lower()


def test_supplied_rejects_sofr_path_point_missing_time():
    """A path point missing 'time' is rejected by Pydantic."""
    bad_path = [{"value": 0.06}]  # time missing
    bad = {**SUPPLIED_BODY, "supplied": {**VALID_SUPPLIED_BODY, "sofr_path": bad_path}}
    with pytest.raises(ValidationError) as exc:
        RunRequest(**bad)
    assert "time" in str(exc.value).lower()


def test_supplied_rejects_non_numeric_fixed_rate():
    """swap_now_fixed must coerce to float; a non-numeric string is rejected."""
    bad = {**SUPPLIED_BODY, "supplied": {**VALID_SUPPLIED_BODY, "swap_now_fixed": "not_a_number"}}
    with pytest.raises(ValidationError) as exc:
        RunRequest(**bad)
    assert "swap_now_fixed" in str(exc.value)


def test_supplied_missing_required_fixed_rate_rejected():
    """swap_later_fixed is required by the model."""
    broken = {k: v for k, v in VALID_SUPPLIED_BODY.items() if k != "swap_later_fixed"}
    bad = {**SUPPLIED_BODY, "supplied": broken}
    with pytest.raises(ValidationError) as exc:
        RunRequest(**bad)
    assert "swap_later_fixed" in str(exc.value)


# ───────────────────────────────────────────────────────────────────────
# _build_initial_state — the route-handler-extracted helper
# ───────────────────────────────────────────────────────────────────────

def test_build_initial_state_v1_shape_has_no_supplied_key():
    """V1 shape produces V1 initial_state — no 'supplied' key polluting state."""
    req = RunRequest(**V1_BODY)
    state = _build_initial_state(req, thread_id="thread-test-1")

    assert state["prompt"] == V1_BODY["prompt"]
    assert state["private_loan_doc"] == V1_BODY["loan_doc"]
    assert state["thread_id"] == "thread-test-1"
    assert state["retry_count"] == 0
    assert state["validation_errors"] == []
    assert state["audit_log"] == []
    assert "supplied" not in state, (
        "V1 baseline must not carry a 'supplied' key — composer would still see "
        "profile.mode='derived' but the presence of state['supplied'] is documented "
        "in test_derived_mode_ignores_supplied_in_state as a defensive guarantee, "
        "not a normal state."
    )


def test_build_initial_state_lifts_supplied_block():
    """Supplied request → state['supplied'] populated as a plain dict."""
    req = RunRequest(**SUPPLIED_BODY)
    state = _build_initial_state(req, thread_id="thread-test-2")

    assert "supplied" in state
    s = state["supplied"]
    assert isinstance(s, dict), "state['supplied'] must be a plain dict, not a Pydantic model"
    assert s["swap_now_fixed"]   == 0.0502
    assert s["swap_later_fixed"] == 0.0585
    assert len(s["sofr_path"]) == 3
    # Path points are also plain dicts (model_dump is recursive).
    assert isinstance(s["sofr_path"][0], dict)
    assert s["sofr_path"][0] == {"time": "2026-02-28T00:00:00", "value": 0.0602}


def test_build_initial_state_thread_id_propagates():
    """thread_id from the route handler lands in state."""
    req = RunRequest(**V1_BODY)
    state = _build_initial_state(req, thread_id="thread-custom-xyz")
    assert state["thread_id"] == "thread-custom-xyz"


# ───────────────────────────────────────────────────────────────────────
# Cross-module contract: API output → composer input
# ───────────────────────────────────────────────────────────────────────

def test_api_supplied_shape_passes_composer_validation():
    """The dict produced by the API edge satisfies the composer's contract.

    This is the integration glue: if the API model changes shape (key rename,
    type change) but the composer still expects the old shape, this test fails
    fast. The two modules share one contract — this test enforces it.
    """
    req = RunRequest(**SUPPLIED_BODY)
    state = _build_initial_state(req, thread_id="thread-contract")

    # Must not raise. _validate_supplied_block is the composer's contract.
    _validate_supplied_block(state["supplied"])


def test_api_supplied_dict_is_independent_of_pydantic_model():
    """model_dump() returns a plain dict — mutating it doesn't leak back to the model.

    Defensive: ensures the graph state is a regular dict that can be checkpointed
    by LangGraph's serializer (Pydantic models in state would require a custom
    serializer).
    """
    req = RunRequest(**SUPPLIED_BODY)
    state = _build_initial_state(req, thread_id="thread-isolation")

    state["supplied"]["swap_now_fixed"] = 0.9999
    # The original Pydantic model is unchanged.
    assert req.supplied.swap_now_fixed == 0.0502
