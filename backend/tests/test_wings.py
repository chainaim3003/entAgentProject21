"""
test_wings.py — Golden-set evals for the reasoning agents (N1 Intake + N5 Interpretation).

Per design, wing evals are tractable BECAUSE the knot is deterministic — we can test
extraction and interpretation in isolation against fixed golden inputs.

These tests require GEMINI_API_KEY to be set with a real key. They are SKIPPED by default
when the key is the placeholder used by test_knot.py. Run with a real key locally:

    GEMINI_API_KEY=<real-key> pytest backend/tests/test_wings.py
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _gemini_available() -> bool:
    key = os.environ.get("GEMINI_API_KEY", "")
    return bool(key) and key != "test-not-used"


# Provide stub values for the OTHER required env vars so config.py loads in test mode.
os.environ.setdefault("DRAPS_MCP_URL", "http://test-not-used")
os.environ.setdefault("ACTUS_MENTOR_URL", "http://test-not-used")


# ───────────────────────────────────────────────────────────────────────
# Intake (N1) — golden inputs
# ───────────────────────────────────────────────────────────────────────

INTAKE_GOLDEN = [
    {
        "name": "textile_india_us",
        "prompt": "I have a 2-year floating loan financing textile imports from India. Should I hedge?",
        "loan_doc": (
            "Loan agreement: principal USD 1,000,000. Spread 250bps over SOFR. "
            "Term: 24 months. Origination: 2026-01-15. Currency: USD. "
            "Use of proceeds: imports of woven textile fabric from India."
        ),
        "expects": {
            "notional_usd": 1_000_000,
            "spread_bps": 250,
            "term_months": 24,
            "rate_index_substr": "SOFR",
            "commodity_hint_keyword": "textile",
        },
    },
]


@pytest.mark.skipif(not _gemini_available(), reason="GEMINI_API_KEY not set; skipping live Gemini eval.")
@pytest.mark.parametrize("case", INTAKE_GOLDEN, ids=lambda c: c["name"])
def test_intake_extraction(case):
    from reasoning_agents import intake_node

    state = {
        "prompt": case["prompt"],
        "private_loan_doc": case["loan_doc"],
        "audit_log": [],
        "retry_count": 0,
    }
    out = intake_node(state)
    raw = out["raw_inputs"]

    expects = case["expects"]
    assert raw["notional_usd"] == expects["notional_usd"], f"notional: got {raw['notional_usd']}"
    assert raw["spread_bps"] == expects["spread_bps"], f"spread: got {raw['spread_bps']}"
    assert raw["term_months"] == expects["term_months"], f"term: got {raw['term_months']}"
    assert expects["rate_index_substr"] in (raw["rate_index"] or ""), (
        f"rate_index: got {raw['rate_index']}"
    )
    assert expects["commodity_hint_keyword"].lower() in (raw["commodity_hint"] or "").lower(), (
        f"commodity_hint: got {raw['commodity_hint']}"
    )


# ───────────────────────────────────────────────────────────────────────
# Interpretation (N5) — golden simulation results
# ───────────────────────────────────────────────────────────────────────

INTERPRETATION_GOLDEN = [
    {
        "name": "hedge_now_wins",
        "simulation_result": {
            "A_total": 234_150,  # no hedge
            "B_total": 192_275,  # hedge now  (saving = 41,875)
            "C_total": 209_300,  # hedge in 3mo (saving = 24,850)
            "events": [],
        },
        "expects_winner": "B",
    },
    {
        "name": "no_hedge_wins",
        "simulation_result": {
            "A_total": 180_000,  # no hedge
            "B_total": 195_000,  # hedge now is worse
            "C_total": 200_000,
            "events": [],
        },
        "expects_winner": "A",
    },
]


@pytest.mark.skipif(not _gemini_available(), reason="GEMINI_API_KEY not set; skipping live Gemini eval.")
@pytest.mark.parametrize("case", INTERPRETATION_GOLDEN, ids=lambda c: c["name"])
def test_interpretation_winner(case):
    from reasoning_agents import interpretation_node

    state = {
        "simulation_result": case["simulation_result"],
        "audit_log": [],
    }
    out = interpretation_node(state)
    rec = out["recommendation"]
    assert rec["winner"] == case["expects_winner"], (
        f"expected winner {case['expects_winner']}, got {rec['winner']}; "
        f"rationale={rec.get('rationale')[:200]}"
    )
