"""
test_simulation_supplied.py - Iteration 3 deliverable 4c.

Exercises simulation_node's D3 honest-deferral boundary: when state['supplied']
is present, the node raises NotImplementedError naming the DRAPS bridge as the
pending piece, instead of silently calling DRAPS (which would derive the SOFR
path itself, ignoring the caller's supplied numbers and producing a
mislabelled result).

Scope (simulation_node only - no graph, no real DRAPS, no ACTUS):
  - state['supplied'] present + validated_inputs present -> NotImplementedError
    is raised, draps_client.run_simulation is NOT called.
  - The error message names DRAPS, the supplied bridge, and the two viable
    follow-up paths (a) DRAPS-side Postman JS override, (b) skip-DRAPS-and-call-
    ACTUS-direct, so the operator can navigate the choice without re-reading
    the source.
  - Regression: state without 'supplied' (or with 'supplied': None) still
    invokes draps_client.run_simulation and produces simulation_result +
    audit_log as before.
  - Ordering: missing validated_inputs still raises RuntimeError (the wiring-
    bug guard), NOT NotImplementedError. Supplied check fires only after the
    wiring guard.

NO live services required - draps_client is monkeypatched. Safe to run in CI.

RUN:
    cd backend
    .venv\\Scripts\\activate
    pytest tests/test_simulation_supplied.py -v
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
sys.path.insert(0, str(BACKEND_DIR))

import deterministic_agents  # noqa: E402  - target of monkeypatch
from deterministic_agents import simulation_node  # noqa: E402


# -----------------------------------------------------------------------------
# Shared fixtures
# -----------------------------------------------------------------------------

# Minimal validated_inputs matching the shape produced by validator_node.
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

SAMPLE_SUPPLIED = {
    "sofr_path": [
        {"time": "2026-02-28T00:00:00", "value": 0.0602},
        {"time": "2026-05-31T00:00:00", "value": 0.0655},
    ],
    "swap_now_fixed":   0.0502,
    "swap_later_fixed": 0.0585,
}


def _state_with_supplied(**overrides) -> dict:
    """State that satisfies the wiring guard AND carries a supplied block."""
    s = {
        "validated_inputs": copy.deepcopy(SAMPLE_VALIDATED_INPUTS),
        "supplied":         copy.deepcopy(SAMPLE_SUPPLIED),
    }
    s.update(overrides)
    return s


def _state_no_supplied(**overrides) -> dict:
    """State for the regression path: validated_inputs but no supplied block."""
    s = {"validated_inputs": copy.deepcopy(SAMPLE_VALIDATED_INPUTS)}
    s.update(overrides)
    return s


@pytest.fixture
def mock_draps(monkeypatch):
    """Replace draps_client.run_simulation with a recording fake.

    Returns a `calls` dict so tests can assert whether the real DRAPS path
    was taken and inspect what validated payload was forwarded.
    """
    calls: dict = {"count": 0, "last_validated": None}

    def fake_run_simulation(validated):
        calls["count"] += 1
        calls["last_validated"] = validated
        return {
            "A_total": 100_000.0,
            "B_total":  90_000.0,
            "C_total":  85_000.0,
            "events":   [],
        }

    monkeypatch.setattr(
        deterministic_agents.draps_client,
        "run_simulation",
        fake_run_simulation,
    )
    return calls


# -----------------------------------------------------------------------------
# Supplied state -> honest NotImplementedError, DRAPS not called
# -----------------------------------------------------------------------------

def test_supplied_state_raises_not_implemented(mock_draps):
    """state['supplied'] present -> NotImplementedError; draps_client untouched."""
    with pytest.raises(NotImplementedError):
        simulation_node(_state_with_supplied())

    # The DRAPS path must NOT have been reached.
    assert mock_draps["count"] == 0, (
        "draps_client.run_simulation was called despite state['supplied'] being present; "
        "the D3 honest-deferral guard failed to short-circuit."
    )


def test_supplied_state_error_message_names_draps_bridge():
    """The error message names DRAPS and the supplied bridge as pending."""
    with pytest.raises(NotImplementedError) as exc:
        simulation_node(_state_with_supplied())
    msg = str(exc.value)

    assert "DRAPS" in msg, f"DRAPS not named in error message: {msg!r}"
    assert "supplied" in msg.lower(), f"'supplied' not mentioned: {msg!r}"
    assert "bridge" in msg.lower() or "not yet implemented" in msg.lower(), (
        f"deferred-bridge framing missing from message: {msg!r}"
    )


def test_supplied_state_error_message_lists_two_follow_up_paths():
    """Error message lists BOTH viable follow-up paths so the operator can choose.

    Per the handoff: (a) modify DRAPS-side Postman JS to honor a supplied_sofr_path
                     (b) skip DRAPS in supplied mode and call ACTUS directly
    """
    with pytest.raises(NotImplementedError) as exc:
        simulation_node(_state_with_supplied())
    msg = str(exc.value)

    # Loose checks - operator can refine wording later without breaking tests.
    assert "Postman" in msg or "DRAPS-side" in msg, (
        f"path (a) DRAPS-side override not mentioned: {msg!r}"
    )
    assert "ACTUS" in msg, (
        f"path (b) skip-DRAPS-call-ACTUS-direct not mentioned: {msg!r}"
    )


def test_supplied_state_with_truthy_but_unusual_shape_still_raises(mock_draps):
    """Any non-None value for state['supplied'] triggers the guard.

    The supplied-block shape is validated by composer._validate_supplied_block,
    not here. simulation_node's job at this boundary is binary: present -> defer.
    """
    state = _state_no_supplied(supplied={"anything": "at all"})
    with pytest.raises(NotImplementedError):
        simulation_node(state)
    assert mock_draps["count"] == 0


# -----------------------------------------------------------------------------
# Regression: no supplied -> existing DRAPS path runs unchanged
# -----------------------------------------------------------------------------

def test_no_supplied_key_still_calls_draps(mock_draps):
    """State without 'supplied' key -> draps_client.run_simulation called."""
    result = simulation_node(_state_no_supplied())

    assert mock_draps["count"] == 1
    assert mock_draps["last_validated"] == SAMPLE_VALIDATED_INPUTS, (
        "validated_inputs forwarded to DRAPS must be unchanged by the new guard"
    )
    assert result["simulation_result"]["A_total"] == 100_000.0


def test_supplied_None_treated_same_as_absent(mock_draps):
    """'supplied': None -> regression path; the guard checks for 'is not None'."""
    state = _state_no_supplied(supplied=None)
    result = simulation_node(state)

    assert mock_draps["count"] == 1
    assert "simulation_result" in result


def test_no_supplied_audit_log_records_totals(mock_draps):
    """Regression: audit_log entry preserved unchanged from the Iter-1 contract."""
    result = simulation_node(_state_no_supplied())
    entries = result["audit_log"]

    assert len(entries) == 1
    entry = entries[0]
    assert entry["node"] == "simulation"
    # The summary string formats the A/B/C totals; existence + key fields suffice.
    assert "A=" in entry["summary"] and "B=" in entry["summary"] and "C=" in entry["summary"]


# -----------------------------------------------------------------------------
# Ordering: wiring-bug guard still fires first
# -----------------------------------------------------------------------------

def test_missing_validated_inputs_still_raises_runtime_error_not_notimpl(mock_draps):
    """validated_inputs missing AND supplied present -> RuntimeError wins.

    The wiring-bug guard is structural (graph routing should make this
    unreachable); the supplied-deferral is a known-pending boundary. The
    structural error is the more important signal, so it must fire first.
    """
    state = {"supplied": copy.deepcopy(SAMPLE_SUPPLIED)}  # NO validated_inputs

    with pytest.raises(RuntimeError, match="validated_inputs"):
        simulation_node(state)

    # NotImplementedError must NOT be raised here - this is a stricter assertion
    # than just matching RuntimeError because NotImplementedError is not a
    # subclass of RuntimeError, so pytest.raises(RuntimeError) would not catch
    # NotImplementedError anyway. We still want DRAPS untouched.
    assert mock_draps["count"] == 0


def test_missing_validated_inputs_without_supplied_still_raises_runtime_error(mock_draps):
    """Regression: the original wiring-bug guard still triggers when supplied is absent too."""
    state: dict = {}  # neither validated_inputs nor supplied
    with pytest.raises(RuntimeError, match="validated_inputs"):
        simulation_node(state)
    assert mock_draps["count"] == 0
