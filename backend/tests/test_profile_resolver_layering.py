"""
test_profile_resolver_layering.py \u2014 Iteration 2 deliverable 6.

Exercises the real profile_resolver per design-v1-config-architecture.md \u00a74:
candidate-list discovery + deep_merge_in_order. Tests run against the actual
config files on disk (no fixture profile files): _base.json + india-us.json +
india-us-textiles.json.

NO live services required \u2014 pure file I/O + Python. Safe to run in CI.

RUN:
    cd backend
    .venv\\Scripts\\activate
    pytest tests/test_profile_resolver_layering.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
sys.path.insert(0, str(BACKEND_DIR))

from profile_resolver import (  # noqa: E402
    _classify,
    _derive_business_identity,
    deep_merge,
    profile_resolver_node,
)


IDENTITY_IN_US_TEX = {
    "mode": "export_import",
    "exporter": "IN",
    "importer": "US",
    "commodity_gtap": "tex",
}

STATE_IN_US_TEX = {
    "public_market_context": {
        "corridor": {"origin": "IN", "destination": "US"},
        "gtap_commodity_code": "tex",
    },
    "audit_log": [],
}


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Happy path
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def test_resolves_india_us_textiles_to_three_layers():
    """IN-US-tex identity finds all three layers, in most-specific-first order."""
    result = profile_resolver_node(STATE_IN_US_TEX)

    assert result["resolved_risk_profile"] is not None
    assert result["risk_factor_profile_id"] == "india-us-textiles-v1"
    assert result.get("validation_errors") is None

    paths = result["profile_resolution_path"]
    assert len(paths) == 3
    assert "india-us-textiles.json" in paths[0]   # most specific first
    assert "india-us.json"          in paths[1]
    assert "_base.json"             in paths[2]


def test_business_identity_derived_from_market_context():
    """_derive_business_identity translates the N2 corridor shape to canonical identity."""
    identity = _derive_business_identity(STATE_IN_US_TEX["public_market_context"])
    assert identity == IDENTITY_IN_US_TEX


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Merge semantics \u2014 design-v1-config-architecture.md \u00a74
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def test_leaf_profile_id_wins_over_base_profile_id():
    """Most-specific scalar wins: profile_id is the leaf's value, not _base's."""
    result = profile_resolver_node(STATE_IN_US_TEX)
    assert result["resolved_risk_profile"]["profile_id"] == "india-us-textiles-v1"
    # Not "export-import-base" and not "india-us-corridor"


def test_base_layer_contributes_pass_through_to_tariff():
    """tariff.inputs.pass_through comes from _base; both files have 0.20 so it survives merge."""
    result = profile_resolver_node(STATE_IN_US_TEX)
    tariff = _get_component(result["resolved_risk_profile"], "tariff")
    assert tariff["inputs"]["pass_through"] == 0.20


def test_corridor_layer_contributes_sovereign_spread():
    """sovereign.inputs.initial/peak come from the corridor layer (commodity-independent)."""
    result = profile_resolver_node(STATE_IN_US_TEX)
    sovereign = _get_component(result["resolved_risk_profile"], "sovereign")
    assert sovereign["inputs"]["initial"] == 0.0050
    assert sovereign["inputs"]["peak"]    == 0.0070


def test_components_in_canonical_order():
    """Component order: base_sofr, tariff, sovereign, wc \u2014 from _base, preserved through merge."""
    result = profile_resolver_node(STATE_IN_US_TEX)
    names = [c["name"] for c in result["resolved_risk_profile"]["components"]]
    assert names == ["base_sofr", "tariff", "sovereign", "wc"]


def test_tariff_inputs_merged_from_all_layers():
    """tariff.inputs combines _base contributions and leaf contributions."""
    result = profile_resolver_node(STATE_IN_US_TEX)
    inputs = _get_component(result["resolved_risk_profile"], "tariff")["inputs"]
    # From _base
    assert inputs["pass_through"] == 0.20
    assert inputs["stress_timing"] == {
        "months_to_peak": 12,
        "plateau_months":  3,
        "descent_months":  9,
    }
    # From leaf
    assert inputs["tariff_current_pct"]   == 0.50
    assert inputs["tariff_peak_pct"]      == 0.60
    assert inputs["armington_elasticity"] == 3.8


def test_base_sofr_inputs_merged_from_base_and_corridor():
    """base_sofr horizon (from _base) + Fed-path values (from corridor)."""
    result = profile_resolver_node(STATE_IN_US_TEX)
    inputs = _get_component(result["resolved_risk_profile"], "base_sofr")["inputs"]
    # From _base
    assert inputs["months_to_peak"]          == 12
    assert inputs["total_months_assumption"] == 24
    # From corridor (india-us.json)
    assert inputs["initial"] == 0.0450
    assert inputs["peak"]    == 0.0550
    assert inputs["final"]   == 0.0475


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Failure paths \u2014 surface validation_errors, no silent default
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def test_unknown_identity_returns_validation_errors():
    """No matching profile \u2192 None + validation_errors. NEVER silent default to textiles."""
    state = {
        "public_market_context": {
            "corridor": {"origin": "ZZ", "destination": "XX"},
            "gtap_commodity_code": "fake",
        },
        "audit_log": [],
    }
    result = profile_resolver_node(state)

    assert result["resolved_risk_profile"]   is None
    assert result["risk_factor_profile_id"]  is None
    assert result["profile_resolution_path"] == []
    errors = result.get("validation_errors") or []
    assert any("no profile matches" in e for e in errors), (
        f"expected 'no profile matches' in errors; got {errors}"
    )


def test_partial_match_corridor_but_unknown_commodity():
    """Valid corridor (IN-US) + unknown commodity \u2192 corridor + base only (no commodity leaf)."""
    state = {
        "public_market_context": {
            "corridor": {"origin": "IN", "destination": "US"},
            "gtap_commodity_code": "unknown_sector",
        },
        "audit_log": [],
    }
    result = profile_resolver_node(state)

    paths = result["profile_resolution_path"]
    assert len(paths) == 2
    assert "india-us.json" in paths[0]
    assert "_base.json"    in paths[1]
    assert not any("india-us-textiles.json" in p for p in paths)


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Unit tests for the merge primitives (called directly)
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def test_deep_merge_overlay_scalar_wins():
    assert deep_merge({"a": 1, "b": 2}, {"b": 99}) == {"a": 1, "b": 99}


def test_deep_merge_recurses_into_nested_dicts():
    base    = {"x": {"a": 1, "b": 2}}
    overlay = {"x": {"b": 99, "c": 3}}
    assert deep_merge(base, overlay) == {"x": {"a": 1, "b": 99, "c": 3}}


def test_deep_merge_components_by_name():
    """Components merge by name: base order first, then overlay-only extras, overlay wins."""
    base    = {"components": [{"name": "a", "v": 1}, {"name": "b", "v": 2}]}
    overlay = {"components": [{"name": "b", "v": 99}, {"name": "c", "v": 3}]}
    result  = deep_merge(base, overlay)

    by_name = {c["name"]: c for c in result["components"]}
    assert by_name["a"]["v"] ==  1  # base only \u2014 preserved
    assert by_name["b"]["v"] == 99  # overlay wins
    assert by_name["c"]["v"] ==  3  # overlay only \u2014 appended

    order = [c["name"] for c in result["components"]]
    assert order == ["a", "b", "c"]


def test_classify_strict_layer_matching():
    """_classify returns the correct layer (or None) for each applies_to shape."""
    identity = IDENTITY_IN_US_TEX
    assert _classify({"mode": "export_import"}, identity) == "base"
    assert _classify(
        {"mode": "export_import", "exporter": "IN", "importer": "US"},
        identity,
    ) == "corridor"
    assert _classify(
        {"mode": "export_import", "exporter": "IN", "importer": "US", "commodity_gtap": "tex"},
        identity,
    ) == "commodity"

    # No match: wrong exporter
    assert _classify(
        {"mode": "export_import", "exporter": "CN", "importer": "US"}, identity
    ) is None
    # No match: missing mode
    assert _classify({"exporter": "IN", "importer": "US"}, identity) is None


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Helpers
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def _get_component(profile: dict, name: str) -> dict:
    for c in profile.get("components") or []:
        if c.get("name") == name:
            return c
    raise AssertionError(f"component {name!r} not found in profile")
