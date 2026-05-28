"""
test_composer_derived.py — Iteration 4 deliverable.

Exercises the composer's `mode='derived' + dispatch='draps_v1'` path with the
real profile_resolver loading from disk, parametrised over the two end-to-end
shipped corridors:

  • india-us-textiles    (Iteration 1 — the byte-equality anchor)
  • vietnam-us-textiles  (Iteration 4 — the new corridor authored this iter)

Per design-v1-iteration-plan.md §"ITERATION 4 — New Corridor / Commodity":

  > Acceptance:
  > - New profile runs end-to-end, produces sensible A/B/C.
  > - The new profile is unit-tested with a known-good fixture (capture the first
  >   run's outputs, freeze as the regression fixture for that profile).
  > - Byte-equality test for India-US-tex still green.

The "known-good fixture" for vietnam-us-textiles is FROZEN INLINE as the
EXPECTED_MERGE table below — capturing the values that should fall out of the
deep merge of _base.json + vietnam-us.json + vietnam-us-textiles.json. Any
unintended drift in those files (or in the merge logic) breaks these tests.

The byte-equality lock for india-us-textiles remains test_byte_equality_v1.py
(live DRAPS+ACTUS roundtrip). This file is the COMPOSER-LEVEL parallel:
no live services, no HTTP, no Docker — pure resolver+composer unit testing
that proves the architecture is corridor-agnostic.

NO live services required — pure file I/O + Python. Safe to run in CI.

RUN:
    cd backend
    .venv\\Scripts\\activate
    pytest tests/test_composer_derived.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
sys.path.insert(0, str(BACKEND_DIR))

from composer import composer_node  # noqa: E402
from profile_resolver import profile_resolver_node  # noqa: E402


# ──────────────────────────────────────────────────────────────────────
# Frozen expected values — the "known-good fixture" per iteration plan
# ──────────────────────────────────────────────────────────────────────
# Each row captures what the deep-merge of _base + corridor + commodity SHOULD
# produce. If any input file drifts (or the merge logic does), these assertions
# will catch it. Comments inline cite which file each value comes from.

EXPECTED_MERGE: dict[str, dict] = {
    "india-us-textiles-v1": {
        "applies_to": {
            "mode": "export_import",
            "exporter": "IN",
            "importer": "US",
            "commodity_gtap": "tex",
        },
        "mode": "derived",            # from _base.json
        "dispatch": "draps_v1",       # from _base.json
        "loan_spread_default": 0.025, # from _base.json (echoed by leaf)
        # base_sofr: FED_PATH from corridor india-us.json (same in leaf)
        "base_sofr": {
            "initial": 0.0450,
            "peak":    0.0550,
            "final":   0.0475,
            "months_to_peak":          12,
            "total_months_assumption": 24,
        },
        # tariff: from leaf india-us-textiles.json + _base.json
        "tariff": {
            "tariff_current_pct":   0.50,
            "tariff_peak_pct":      0.60,
            "armington_elasticity": 3.8,
            "pass_through":         0.20,
        },
        # sovereign: from corridor india-us.json (BBB rating)
        "sovereign": {
            "initial": 0.0050,
            "peak":    0.0070,
        },
        # wc: from leaf india-us-textiles.json
        "wc": {
            "initial": 0.0030,
            "peak":    0.0050,
        },
    },
    "vietnam-us-textiles-v1": {
        "applies_to": {
            "mode": "export_import",
            "exporter": "VN",
            "importer": "US",
            "commodity_gtap": "tex",
        },
        "mode": "derived",
        "dispatch": "draps_v1",
        "loan_spread_default": 0.025,
        # base_sofr: identical to india-us because importer=US in both
        "base_sofr": {
            "initial": 0.0450,
            "peak":    0.0550,
            "final":   0.0475,
            "months_to_peak":          12,
            "total_months_assumption": 24,
        },
        # tariff: scenario inputs identical to india-us-textiles (isolates the corridor effect on A/B/C)
        "tariff": {
            "tariff_current_pct":   0.50,
            "tariff_peak_pct":      0.60,
            "armington_elasticity": 3.8,
            "pass_through":         0.20,
        },
        # sovereign: from corridor vietnam-us.json (BB+ S&P, Aug 2025)
        # This is the contrast point with india-us — corridor-level difference shows.
        "sovereign": {
            "initial": 0.0100,
            "peak":    0.0140,
        },
        # wc: from leaf vietnam-us-textiles.json (same textile DSO commodity-economics as india-us)
        "wc": {
            "initial": 0.0030,
            "peak":    0.0050,
        },
    },
}


# State builder: maps corridor identity → public_market_context state.
def _state_for(exporter: str, importer: str, commodity: str) -> dict:
    return {
        "public_market_context": {
            "corridor": {"origin": exporter, "destination": importer},
            "gtap_commodity_code": commodity,
        },
        "audit_log": [],
    }


# A minimal validated_inputs body — composer deep-copies it into knot_payload.
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
        "tariff_assumption_pct": 0.5,
        "rate_curve_index": "USD-SOFR-FORWARD",
    },
}

SAMPLE_HEDGE_SPEC = {"spec_id": "default-3-scenario"}


# (corridor identity tuple, expected profile_id) — drives the parametrize.
CORRIDOR_CASES = [
    pytest.param(("IN", "US", "tex"), "india-us-textiles-v1",   id="india-us-textiles"),
    pytest.param(("VN", "US", "tex"), "vietnam-us-textiles-v1", id="vietnam-us-textiles"),
]


def _get_component(profile: dict, name: str) -> dict:
    for c in profile.get("components") or []:
        if c.get("name") == name:
            return c
    raise AssertionError(f"component {name!r} not found in profile")


# ──────────────────────────────────────────────────────────────────────
# Resolver-level assertions: the layered merge produces expected outputs
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("identity,profile_id", CORRIDOR_CASES)
def test_three_layer_resolution_succeeds(identity, profile_id):
    """Both corridors resolve to exactly three layers, leaf wins on profile_id."""
    exp, imp, com = identity
    result = profile_resolver_node(_state_for(exp, imp, com))

    assert result["resolved_risk_profile"] is not None
    assert result["risk_factor_profile_id"] == profile_id
    assert result.get("validation_errors") is None
    paths = result["profile_resolution_path"]
    assert len(paths) == 3, f"expected 3 layers for {profile_id}, got {paths}"
    # Most-specific first.
    assert profile_id.split("-v1")[0] in paths[0]   # e.g. 'india-us-textiles' or 'vietnam-us-textiles' in path[0]
    assert "_base.json" in paths[2]


@pytest.mark.parametrize("identity,profile_id", CORRIDOR_CASES)
def test_resolved_profile_applies_to_matches_identity(identity, profile_id):
    """applies_to on the merged profile reflects the leaf's discriminator."""
    exp, imp, com = identity
    result = profile_resolver_node(_state_for(exp, imp, com))
    profile = result["resolved_risk_profile"]
    expected = EXPECTED_MERGE[profile_id]["applies_to"]
    assert profile["applies_to"] == expected


@pytest.mark.parametrize("identity,profile_id", CORRIDOR_CASES)
def test_resolved_mode_and_dispatch_inherit_from_base(identity, profile_id):
    """mode='derived' and dispatch='draps_v1' come from _base.json for both corridors."""
    exp, imp, com = identity
    result = profile_resolver_node(_state_for(exp, imp, com))
    profile = result["resolved_risk_profile"]
    expected = EXPECTED_MERGE[profile_id]
    assert profile["mode"]     == expected["mode"]
    assert profile["dispatch"] == expected["dispatch"]


@pytest.mark.parametrize("identity,profile_id", CORRIDOR_CASES)
def test_resolved_base_sofr_matches_frozen_fixture(identity, profile_id):
    """base_sofr inputs identical across corridors (importer=US for both)."""
    exp, imp, com = identity
    result = profile_resolver_node(_state_for(exp, imp, com))
    inputs = _get_component(result["resolved_risk_profile"], "base_sofr")["inputs"]
    expected = EXPECTED_MERGE[profile_id]["base_sofr"]
    for k, v in expected.items():
        assert inputs[k] == v, f"base_sofr.{k}: actual={inputs[k]}, expected={v}"


@pytest.mark.parametrize("identity,profile_id", CORRIDOR_CASES)
def test_resolved_tariff_matches_frozen_fixture(identity, profile_id):
    """tariff scenario inputs match frozen values (held identical across corridors in Iter-4)."""
    exp, imp, com = identity
    result = profile_resolver_node(_state_for(exp, imp, com))
    inputs = _get_component(result["resolved_risk_profile"], "tariff")["inputs"]
    expected = EXPECTED_MERGE[profile_id]["tariff"]
    for k, v in expected.items():
        assert inputs[k] == v, f"tariff.{k}: actual={inputs[k]}, expected={v}"


@pytest.mark.parametrize("identity,profile_id", CORRIDOR_CASES)
def test_resolved_sovereign_matches_frozen_fixture(identity, profile_id):
    """sovereign spread differs by corridor — this is the architectural point of Iter-4."""
    exp, imp, com = identity
    result = profile_resolver_node(_state_for(exp, imp, com))
    inputs = _get_component(result["resolved_risk_profile"], "sovereign")["inputs"]
    expected = EXPECTED_MERGE[profile_id]["sovereign"]
    for k, v in expected.items():
        assert inputs[k] == v, f"sovereign.{k}: actual={inputs[k]}, expected={v}"


@pytest.mark.parametrize("identity,profile_id", CORRIDOR_CASES)
def test_resolved_wc_matches_frozen_fixture(identity, profile_id):
    """wc inputs match frozen values (commodity-economic, same across corridors for tex)."""
    exp, imp, com = identity
    result = profile_resolver_node(_state_for(exp, imp, com))
    inputs = _get_component(result["resolved_risk_profile"], "wc")["inputs"]
    expected = EXPECTED_MERGE[profile_id]["wc"]
    for k, v in expected.items():
        assert inputs[k] == v, f"wc.{k}: actual={inputs[k]}, expected={v}"


# ──────────────────────────────────────────────────────────────────────
# Architectural-corridor-agnosticism assertions: the contrast that Iter-4 proves
# ──────────────────────────────────────────────────────────────────────

def test_vietnam_sovereign_strictly_wider_than_india_sovereign():
    """Iter-4 architectural point: BB+ Vietnam sovereign spread is wider than BBB India.

    If this ever flips, it means either (a) the rating data has been re-sourced
    and the test should be updated alongside, or (b) one of the corridor files
    has drifted in a way that breaks the demo narrative. Either way, flag.
    """
    in_result = profile_resolver_node(_state_for("IN", "US", "tex"))
    vn_result = profile_resolver_node(_state_for("VN", "US", "tex"))

    in_sov = _get_component(in_result["resolved_risk_profile"], "sovereign")["inputs"]
    vn_sov = _get_component(vn_result["resolved_risk_profile"], "sovereign")["inputs"]

    assert vn_sov["initial"] > in_sov["initial"], (
        f"VN BB+ base spread {vn_sov['initial']} should be wider than "
        f"IN BBB base spread {in_sov['initial']}"
    )
    assert vn_sov["peak"] > in_sov["peak"], (
        f"VN BB+ peak spread {vn_sov['peak']} should be wider than "
        f"IN BBB peak spread {in_sov['peak']}"
    )


def test_us_fed_path_identical_across_corridors():
    """base_sofr inputs come from the US-side, so VN-US and IN-US must match exactly."""
    in_result = profile_resolver_node(_state_for("IN", "US", "tex"))
    vn_result = profile_resolver_node(_state_for("VN", "US", "tex"))

    in_sofr = _get_component(in_result["resolved_risk_profile"], "base_sofr")["inputs"]
    vn_sofr = _get_component(vn_result["resolved_risk_profile"], "base_sofr")["inputs"]

    assert in_sofr == vn_sofr, (
        f"base_sofr (US Fed path) must be corridor-independent;\n"
        f"  IN-US: {in_sofr}\n"
        f"  VN-US: {vn_sofr}"
    )


def test_armington_elasticity_identical_across_corridors():
    """Armington is commodity-economic (tex=3.8), must be the same for any X-US-tex corridor."""
    in_result = profile_resolver_node(_state_for("IN", "US", "tex"))
    vn_result = profile_resolver_node(_state_for("VN", "US", "tex"))

    in_tariff = _get_component(in_result["resolved_risk_profile"], "tariff")["inputs"]
    vn_tariff = _get_component(vn_result["resolved_risk_profile"], "tariff")["inputs"]

    assert in_tariff["armington_elasticity"] == 3.8
    assert vn_tariff["armington_elasticity"] == 3.8


# ──────────────────────────────────────────────────────────────────────
# Composer-level assertions: the resolved profile feeds the composer
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("identity,profile_id", CORRIDOR_CASES)
def test_composer_builds_knot_payload_for_both_corridors(identity, profile_id):
    """End-to-end resolver→composer: both corridors produce knot_payload with provenance."""
    exp, imp, com = identity

    # Step 1: resolve the profile from disk.
    res = profile_resolver_node(_state_for(exp, imp, com))
    profile = res["resolved_risk_profile"]
    assert profile is not None

    # Step 2: feed to the composer.
    composer_state = {
        "validated_inputs": SAMPLE_VALIDATED_INPUTS,
        "resolved_risk_profile": profile,
        "resolved_hedge_spec":   SAMPLE_HEDGE_SPEC,
    }
    result = composer_node(composer_state)
    kp = result["knot_payload"]

    # Knot payload preserves the validated_inputs structure.
    assert "loan"   in kp
    assert "market" in kp
    # Iter-1 derived path: no supplied block on knot_payload.
    assert "supplied" not in kp
    # Provenance stamp identifies the corridor.
    prov = kp["_provenance"]
    assert prov["mode"]          == "derived"
    assert prov["dispatch"]      == "draps_v1"
    assert prov["profile_id"]    == profile_id
    assert prov["hedge_spec_id"] == "default-3-scenario"
    assert "DRAPS" in prov["source_summary"]


@pytest.mark.parametrize("identity,profile_id", CORRIDOR_CASES)
def test_composer_audit_log_records_profile_id(identity, profile_id):
    """The audit entry surfaces the resolved profile_id for downstream consumers."""
    exp, imp, com = identity
    res = profile_resolver_node(_state_for(exp, imp, com))
    profile = res["resolved_risk_profile"]

    result = composer_node({
        "validated_inputs": SAMPLE_VALIDATED_INPUTS,
        "resolved_risk_profile": profile,
        "resolved_hedge_spec":   SAMPLE_HEDGE_SPEC,
    })

    entries = result["audit_log"]
    assert len(entries) == 1
    out = entries[0]["output"]
    assert out["mode"]       == "derived"
    assert out["dispatch"]   == "draps_v1"
    assert out["profile_id"] == profile_id
    assert "loan"   in out["knot_payload_keys"]
    assert "market" in out["knot_payload_keys"]


# ──────────────────────────────────────────────────────────────────────
# Cross-pollination guard: adding VN must not have changed IN resolution
# ──────────────────────────────────────────────────────────────────────

def test_adding_vietnam_files_does_not_affect_india_resolution():
    """The Iter-4 byte-equality side-condition: IN-US-tex must still resolve to
    the same files in the same order as before VN files landed.

    This is the lighter sibling of test_byte_equality_v1.py — it doesn't roundtrip
    through DRAPS but it does verify the resolver layering for IN-US-tex.
    """
    result = profile_resolver_node(_state_for("IN", "US", "tex"))
    paths = result["profile_resolution_path"]
    assert len(paths) == 3
    assert "india-us-textiles.json" in paths[0]
    assert "india-us.json"          in paths[1]
    assert "_base.json"             in paths[2]
    # The Vietnam files must NOT have leaked into the resolution path.
    for p in paths:
        assert "vietnam" not in p.lower(), (
            f"Vietnam file leaked into India resolution: {p}"
        )
