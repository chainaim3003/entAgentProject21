"""
test_simulation_v2_direct.py - Iteration 6a deliverable D3.

Exercises simulation_node's v2_direct compute+ACTUS path end-to-end through the
node (so it covers BOTH the new branch in deterministic_agents.simulation_node
AND actus_client.run_v2_direct), with the ACTUS HTTP layer monkeypatched.

When the composer ran dispatch='v2_direct' (mode='derived') it derived the SOFR
path + the two swap fixed rates in V2 and stamped them onto
knot_payload['v2_direct']. simulation_node detects that, calls
actus_client.run_v2_direct, which builds the A/B/C scenario batches and POSTs each
to ACTUS /eventsBatch. This test replaces actus_client._post_events_batch with a
fake that returns canned IP (+ deliberate non-IP noise) events keyed by
contractID, so no live ACTUS is required.

Aggregation contract under test (replicated from the authoritative Postman
test-scripts in DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json):
  A_total = abs(sum IP payoff on LOAN-FLOAT-ONLY)            A_swap = 0
  B_total = abs(IP on LOAN-FLOAT-B) - signed(IP on SWAP-NOW-B)
  C_total = abs(IP on LOAN-FLOAT-C) - signed(IP on SWAP-LATER-C)
With the canned numbers below: A=192275, B=192275-41875=150400,
C=192275-24885=167390.

Also asserts:
  - non-IP events (IED/MD/RR) are excluded from every leg's aggregation,
  - the loan leg's nominalInterestRate == _to_fixed4(sofr0 + loan_spread),
  - the scenario-C FLOAT leg picks the SOFR point at swap_start (loan_start +3mo
    here), NOT sofr_path[0],
  - the v2_direct branch short-circuits BEFORE the draps_v1 path (draps not called),
  - the audit entry records dispatch='v2_direct'.

NO live services required. Safe to run in CI.

RUN:
    cd backend
    .venv\\Scripts\\activate
    pytest tests/test_simulation_v2_direct.py -v
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
sys.path.insert(0, str(BACKEND_DIR))

import actus_client  # noqa: E402  - for _to_fixed4 + as monkeypatch target
import deterministic_agents  # noqa: E402  - target of monkeypatch
from deterministic_agents import simulation_node  # noqa: E402


# -----------------------------------------------------------------------------
# Shared fixtures
# -----------------------------------------------------------------------------

# Minimal validated_inputs - the v2_direct branch does NOT read it, but the
# wiring-bug guard at the top of simulation_node requires it to be non-None.
SAMPLE_VALIDATED_INPUTS = {
    "loan": {
        "notional_usd": 1_000_000.0,
        "spread_bps": 250.0,
        "term_months": 24,
        "start_date": "2025-01-01",
        "rate_index": "SOFR",
    },
    "market": {
        "gtap_commodity_code": "tex",
        "corridor": {"origin": "India", "destination": "United States"},
        "tariff_assumption_pct": 0.5,
        "rate_curve_index": "USD-SOFR-FORWARD",
    },
}

# sofr0 = 0.04 ; the +3mo point (2025-04-01) carries a DISTINCT value 0.045 so we
# can prove the scenario-C FLOAT lookup selects it rather than sofr_path[0].
SAMPLE_V2_DIRECT = {
    "sofr_path": [
        {"time": "2025-01-01T00:00:00", "value": 0.04},   # [0] = sofr0
        {"time": "2025-04-01T00:00:00", "value": 0.045},  # +3mo -> swap_start
        {"time": "2025-07-01T00:00:00", "value": 0.05},
        {"time": "2026-01-01T00:00:00", "value": 0.055},
    ],
    "swap_now_fixed": 0.05,
    "swap_later_fixed": 0.052,
}

SAMPLE_LOAN = {
    "notional_usd": 1_000_000.0,
    "spread_bps": 250.0,            # -> loan_spread = 0.025
    "term_months": 24,
    "start_date": "2025-01-01",
    "rate_index": "SOFR",
}

# scenarios sorted ascending by swap_offset_months -> [0]=now, [1]=later=3 months.
SAMPLE_HEDGE_SPEC = {
    "scenarios": [
        {"swap_offset_months": 0},
        {"swap_offset_months": 3},
    ]
}

SOFR0 = 0.04
LOAN_SPREAD = 0.025          # 250 bps / 10000
SWAP_START_SOFR = 0.045      # value at loan_start +3mo

# Canned IP events. Loan legs abs-sum to 192275; SWAP-NOW signed-sums to 41875;
# SWAP-LATER signed-sums to 24885. Loan IP payoffs are negative (interest paid);
# _loan_leg_abs takes abs so the sign is irrelevant for the loan total.
_LOAN_IP = [
    {"type": "IP", "payoff": -100_000.0},
    {"type": "IP", "payoff": -92_275.0},
]
# Deliberate non-IP noise with LARGE payoffs: if any of these leaked into the
# aggregation the totals would be wildly off, so the exact-total asserts double
# as the non-IP-exclusion test.
_NON_IP_NOISE = [
    {"type": "IED", "payoff": -1_000_000.0},
    {"type": "MD", "payoff": 1_000_000.0},
    {"type": "RR", "payoff": 55_555.0},
]
CANNED_EVENTS = {
    "LOAN-FLOAT-ONLY": _LOAN_IP + _NON_IP_NOISE,
    "LOAN-FLOAT-B": _LOAN_IP + _NON_IP_NOISE,
    "LOAN-FLOAT-C": _LOAN_IP + _NON_IP_NOISE,
    "SWAP-NOW-B": [
        {"type": "IP", "payoff": 25_000.0},
        {"type": "IP", "payoff": 16_875.0},
    ] + _NON_IP_NOISE,
    "SWAP-LATER-C": [
        {"type": "IP", "payoff": 12_000.0},
        {"type": "IP", "payoff": 12_885.0},
    ] + _NON_IP_NOISE,
}

EXPECTED = {
    "A_total": 192_275.0, "A_loan": 192_275.0, "A_swap": 0.0,
    "B_total": 150_400.0, "B_loan": 192_275.0, "B_swap": 41_875.0,
    "C_total": 167_390.0, "C_loan": 192_275.0, "C_swap": 24_885.0,
}


def _knot(**overrides) -> dict:
    k = {
        "loan": copy.deepcopy(SAMPLE_LOAN),
        "v2_direct": copy.deepcopy(SAMPLE_V2_DIRECT),
    }
    k.update(overrides)
    return k


def _state(**overrides) -> dict:
    s = {
        "validated_inputs": copy.deepcopy(SAMPLE_VALIDATED_INPUTS),
        "knot_payload": _knot(),
        "resolved_hedge_spec": copy.deepcopy(SAMPLE_HEDGE_SPEC),
    }
    s.update(overrides)
    return s


@pytest.fixture
def mock_actus(monkeypatch):
    """Replace actus_client._post_events_batch with a recording fake.

    The fake reads the contractIDs present in each scenario payload and returns
    one response-contract per payload-contract, with canned events. It records
    every payload it received so tests can inspect the wire shape (rates, dates).
    """
    captured: dict = {"payloads": [], "count": 0}

    def fake_post(payload):
        captured["count"] += 1
        captured["payloads"].append(payload)
        contracts = payload.get("contracts") or []
        out = []
        for c in contracts:
            cid = c.get("contractID")
            assert cid in CANNED_EVENTS, (
                f"fake_post received an unexpected contractID {cid!r}; "
                f"known: {sorted(CANNED_EVENTS)}"
            )
            out.append({"contractID": cid, "events": copy.deepcopy(CANNED_EVENTS[cid])})
        return out

    monkeypatch.setattr(deterministic_agents.actus_client, "_post_events_batch", fake_post)
    return captured


@pytest.fixture
def mock_draps(monkeypatch):
    """Recording fake for draps_client.run_simulation - must NOT be called on the
    v2_direct path (it short-circuits before the draps_v1 logic)."""
    calls = {"count": 0}

    def fake_run_simulation(validated):
        calls["count"] += 1
        return {"A_total": 0.0, "B_total": 0.0, "C_total": 0.0, "events": []}

    monkeypatch.setattr(deterministic_agents.draps_client, "run_simulation", fake_run_simulation)
    return calls


def _scenario_payload(captured, *contract_ids):
    """Return the captured payload whose contract set matches contract_ids exactly."""
    want = set(contract_ids)
    for p in captured["payloads"]:
        have = {c.get("contractID") for c in (p.get("contracts") or [])}
        if have == want:
            return p
    raise AssertionError(
        f"no captured payload with contract set {want}; "
        f"saw {[ {c.get('contractID') for c in (p.get('contracts') or [])} for p in captured['payloads'] ]}"
    )


# -----------------------------------------------------------------------------
# A/B/C totals
# -----------------------------------------------------------------------------

def test_v2_direct_abc_totals(mock_actus, mock_draps):
    """A=192275, B=150400, C=167390 with the documented swap deductions."""
    out = simulation_node(_state())
    sim = out["simulation_result"]

    for key, expected in EXPECTED.items():
        assert sim[key] == expected, f"{key}: expected {expected}, got {sim[key]}"

    # Exactly three POSTs (A, B, C); draps_v1 path never entered.
    assert mock_actus["count"] == 3
    assert mock_draps["count"] == 0, "v2_direct must NOT fall through to draps_client.run_simulation"


def test_a_scenario_has_no_swap(mock_actus, mock_draps):
    sim = simulation_node(_state())["simulation_result"]
    assert sim["A_swap"] == 0.0
    assert sim["A_total"] == sim["A_loan"] == 192_275.0


def test_b_swap_deduction(mock_actus, mock_draps):
    sim = simulation_node(_state())["simulation_result"]
    assert sim["B_swap"] == 41_875.0
    assert sim["B_total"] == sim["B_loan"] - sim["B_swap"] == 150_400.0


def test_c_swap_deduction(mock_actus, mock_draps):
    sim = simulation_node(_state())["simulation_result"]
    assert sim["C_swap"] == 24_885.0
    assert sim["C_total"] == sim["C_loan"] - sim["C_swap"] == 167_390.0


# -----------------------------------------------------------------------------
# Non-IP exclusion
# -----------------------------------------------------------------------------

def test_non_ip_events_excluded_from_aggregation(mock_actus, mock_draps):
    """The canned events carry IED/MD/RR noise with payoffs up to +/-1,000,000.

    If any non-IP event leaked into _loan_leg_abs / _swap_leg_signed the totals
    would shift by hundreds of thousands. Exact totals prove IP-only filtering.
    """
    sim = simulation_node(_state())["simulation_result"]
    # Loan abs over IP-only = 192275; the noise (abs would add 2,055,555) is absent.
    assert sim["A_loan"] == 192_275.0
    assert sim["B_loan"] == 192_275.0
    assert sim["C_loan"] == 192_275.0
    # Swap signed over IP-only; noise signed sum (+55,555) is absent.
    assert sim["B_swap"] == 41_875.0
    assert sim["C_swap"] == 24_885.0


# -----------------------------------------------------------------------------
# Wire-shape: loan rate and scenario-C FLOAT lookup
# -----------------------------------------------------------------------------

def test_loan_nominal_rate_is_sofr0_plus_spread(mock_actus, mock_draps):
    """Every loan PAM carries nominalInterestRate == _to_fixed4(sofr0 + loan_spread)."""
    simulation_node(_state())
    expected_rate = actus_client._to_fixed4(SOFR0 + LOAN_SPREAD)  # _to_fixed4(0.065) -> "0.0650"
    assert expected_rate == "0.0650"

    payload_a = _scenario_payload(mock_actus, "LOAN-FLOAT-ONLY")
    loan = next(c for c in payload_a["contracts"] if c["contractID"] == "LOAN-FLOAT-ONLY")
    assert loan["nominalInterestRate"] == expected_rate


def test_scenario_c_float_leg_picks_swap_start_point_not_first(mock_actus, mock_draps):
    """SWAP-LATER-C FLOAT leg uses the SOFR value at swap_start (loan_start +3mo),
    i.e. 0.045, NOT sofr_path[0] (0.04)."""
    simulation_node(_state())
    payload_c = _scenario_payload(mock_actus, "LOAN-FLOAT-C", "SWAP-LATER-C")
    swap = next(c for c in payload_c["contracts"] if c["contractID"] == "SWAP-LATER-C")

    float_leg = next(
        leg for leg in swap["contractStructure"] if leg.get("referenceRole") == "SEL"
    )
    rate = float_leg["object"]["nominalInterestRate"]
    assert rate == actus_client._to_fixed4(SWAP_START_SOFR) == "0.0450"
    assert rate != actus_client._to_fixed4(SOFR0), "FLOAT leg wrongly fell back to sofr_path[0]"


# -----------------------------------------------------------------------------
# Audit / branch detection
# -----------------------------------------------------------------------------

def test_audit_entry_records_v2_direct_dispatch(mock_actus, mock_draps):
    out = simulation_node(_state())
    entries = out["audit_log"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["node"] == "simulation"
    assert entry["output"]["dispatch"] == "v2_direct"
    assert "(v2_direct)" in entry["summary"]
    assert "A=" in entry["summary"] and "B=" in entry["summary"] and "C=" in entry["summary"]


def test_carried_through_rates_present(mock_actus, mock_draps):
    """run_v2_direct carries the supplied fixed rates + sofr_path through for N6a."""
    sim = simulation_node(_state())["simulation_result"]
    assert sim["swap_now_fixed_rate"] == 0.05
    assert sim["swap_later_fixed_rate"] == 0.052
    assert sim["sofr_path"] == SAMPLE_V2_DIRECT["sofr_path"]


# -----------------------------------------------------------------------------
# Guard ordering: v2_direct does not disturb the wiring-bug guard
# -----------------------------------------------------------------------------

def test_missing_validated_inputs_still_raises_even_with_v2_direct(mock_actus, mock_draps):
    """validated_inputs missing -> RuntimeError (wiring guard) fires first; ACTUS untouched."""
    state = {"knot_payload": _knot(), "resolved_hedge_spec": copy.deepcopy(SAMPLE_HEDGE_SPEC)}
    with pytest.raises(RuntimeError, match="validated_inputs"):
        simulation_node(state)
    assert mock_actus["count"] == 0
