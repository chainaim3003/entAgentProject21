"""
test_composer_derived_domestic.py — Iteration 6 deliverable (Patch 4).

The COMPOSER-LEVEL parallel to test_composer_derived.py, but for the FIRST
domestic profile: it exercises the resolver's domestic branch end-to-end into
the composer's `mode='derived_domestic' + dispatch='v2_direct'` path (Branch 3),
with the real profile_resolver loading from disk and the real shipped hedge
spec (_default.json) loading from disk.

Path under test:
  public_market_context{business_mode=domestic_services, industry=services}
    -> profile_resolver_node  (domestic arm of _classify / _scan_candidates)
       -> resolves us-services.json (sector) over _base_domestic.json (base)
          -> merged profile_id='us-services-v1', mode='derived_domestic', dispatch='v2_direct'
    -> composer_node          (Branch 3: derived_domestic + v2_direct)
       -> _build_sofr_path sums the 4 domestic components per tenor point
       -> _apply_fixed_rate_rule('discount_from_path') derives the two swap fixed rates
          -> knot_payload['v2_direct'] = {sofr_path[9], swap_now_fixed, swap_later_fixed}

SCOPE NOTE (per design-v1-iteration-plan.md §4 "capture the first run's outputs,
freeze as the regression fixture"): this Iter-6 file asserts the STRUCTURE and
the internal RELATIONSHIPS that must hold regardless of the exact synthetic
component numerics — 9 grid points on the correct quarterly grid, fixed rates
derived from the path by the documented discount rule, correct provenance/audit.
The ABSOLUTE 9-point SOFR values are NOT frozen here; the us-services.json inputs
are explicitly flagged in that file's _notes as ILLUSTRATIVE / pending live-source
binding. Freezing the numeric vector as a regression fixture is the Iter-7 extension
of this file (once the snapshot pipelines mature), to avoid locking a regression
gate onto placeholder values.

NO live services required — pure file I/O + Python. Safe to run in CI.

RUN:
    cd backend
    .venv\\Scripts\\activate
    pytest tests/test_composer_derived_domestic.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from composer import composer_node, _round4  # noqa: E402  (_round4: assert fixed-rate relation exactly)
from profile_resolver import profile_resolver_node  # noqa: E402


# ──────────────────────────────────────────────────────────────────────
# Fixtures / constants — all grounded in the actual shipped config files
# ──────────────────────────────────────────────────────────────────────

EXPECTED_PROFILE_ID = "us-services-v1"          # us-services.json: profile_id (leaf wins on merge)
EXPECTED_MODE = "derived_domestic"              # both domestic configs: mode
EXPECTED_DISPATCH = "v2_direct"                 # both domestic configs: dispatch

# Loan anchor for the quarterly tenor grid. The composer's _build_sofr_path
# anchors at validated_inputs['loan']['start_date'] and steps TENOR_STEP_MONTHS=3
# for TENOR_POINTS=9 points. Day is 1 so JS-overflow _add_months stays on the 1st.
LOAN_START = "2026-03-01"

# The exact ISO grid the composer must emit for LOAN_START at 3-month steps.
# These are date-arithmetic facts (independent of the component float formulas),
# so they are safe to assert exactly even though the per-point VALUES are not frozen.
EXPECTED_SOFR_TIMES = [
    "2026-03-01T00:00:00",  # t=0   (loan_start)
    "2026-06-01T00:00:00",  # t=3
    "2026-09-01T00:00:00",  # t=6
    "2026-12-01T00:00:00",  # t=9
    "2027-03-01T00:00:00",  # t=12
    "2027-06-01T00:00:00",  # t=15
    "2027-09-01T00:00:00",  # t=18
    "2027-12-01T00:00:00",  # t=21
    "2028-03-01T00:00:00",  # t=24
]

# _default.json discount params (bps -> fraction). The composer derives:
#   swap_now_fixed   = round4( sofr_at(loan_start + 0mo) - NOW_DISCOUNT   )
#   swap_later_fixed = round4( sofr_at(loan_start + 3mo) - LATER_DISCOUNT )
# With the grid above, sofr_at(loan_start+0) == sofr_path[0] and
# sofr_at(loan_start+3) == sofr_path[1] (lookup returns first point with date >= target).
NOW_DISCOUNT = 100 / 10000    # 0.0100  (swap_now_discount_bps)
LATER_DISCOUNT = 70 / 10000   # 0.0070  (swap_later_discount_bps)

SAMPLE_VALIDATED_INPUTS = {
    "loan": {
        "notional_usd": 1_000_000.0,
        "spread_bps": 250.0,
        "term_months": 24,
        "start_date": LOAN_START,
        "rate_index": "SOFR",
    },
    "market": {
        "rate_curve_index": "USD-SOFR-FORWARD",
    },
}


def _domestic_state() -> dict:
    """public_market_context for the domestic-services audience.

    NOTE: the resolver's _derive_business_identity reads ONLY business_mode +
    industry from this context for the domestic arm. naics_sector and
    rate_curve_index are carried for realism / downstream nodes but are inert to
    the resolver — test_business_identity_ignores_unread_context_fields locks that.
    """
    return {
        "public_market_context": {
            "business_mode": "domestic_services",
            "industry": "services",
            "naics_sector": "54",
            "rate_curve_index": "USD-SOFR-FORWARD",
        },
        "audit_log": [],
    }


def _load_default_hedge_spec() -> dict:
    """Load the real shipped 3-scenario hedge spec from disk.

    Using the on-disk config (not an inline stub) keeps this test honest: if
    _default.json drifts its discount bps or scenario offsets, the derived
    fixed-rate relations below will catch it.
    """
    path = REPO_ROOT / "config" / "hedge-specs" / "_default.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _component_names(profile: dict) -> list[str]:
    return [c.get("name") for c in (profile.get("components") or [])]


# ──────────────────────────────────────────────────────────────────────
# Resolver-level: the domestic branch resolves us-services over _base_domestic
# ──────────────────────────────────────────────────────────────────────

def test_domestic_resolves_to_us_services_two_layers():
    """domestic_services resolves to exactly [us-services.json, _base_domestic.json]."""
    result = profile_resolver_node(_domestic_state())

    assert result.get("validation_errors") is None, result.get("validation_errors")
    assert result["resolved_risk_profile"] is not None
    assert result["risk_factor_profile_id"] == EXPECTED_PROFILE_ID

    paths = result["profile_resolution_path"]
    assert len(paths) == 2, f"expected 2 domestic layers, got {paths}"
    assert "us-services.json" in paths[0], f"sector layer should be most-specific: {paths}"
    assert "_base_domestic.json" in paths[1], f"base layer should be least-specific: {paths}"


def test_domestic_merged_mode_dispatch_and_applies_to():
    """Merged profile carries derived_domestic + v2_direct + the leaf's applies_to."""
    profile = profile_resolver_node(_domestic_state())["resolved_risk_profile"]
    assert profile["mode"] == EXPECTED_MODE
    assert profile["dispatch"] == EXPECTED_DISPATCH
    assert profile["applies_to"] == {"mode": "domestic", "industry": "services"}


def test_domestic_merged_components_in_declared_order():
    """Deep-merge preserves the 4-component domestic skeleton in declared order."""
    profile = profile_resolver_node(_domestic_state())["resolved_risk_profile"]
    assert _component_names(profile) == [
        "base_sofr", "demand_volatility", "payment_cycle", "wc",
    ]


def test_business_identity_ignores_unread_context_fields():
    """Resolver derives identity from business_mode + industry only.

    Locks the fact (verified against profile_resolver._derive_business_identity)
    that naics_sector / rate_curve_index in public_market_context are NOT read
    into business_identity. If a future change starts consuming them, update this.
    """
    identity = profile_resolver_node(_domestic_state())["business_identity"]
    assert identity == {"mode": "domestic_services", "industry": "services"}


# ──────────────────────────────────────────────────────────────────────
# Composer-level: Branch 3 (derived_domestic + v2_direct) builds the SOFR path
# ──────────────────────────────────────────────────────────────────────

def _resolve_then_compose() -> dict:
    profile = profile_resolver_node(_domestic_state())["resolved_risk_profile"]
    assert profile is not None
    return composer_node({
        "validated_inputs": SAMPLE_VALIDATED_INPUTS,
        "resolved_risk_profile": profile,
        "resolved_hedge_spec": _load_default_hedge_spec(),
    })


def test_composer_builds_v2_direct_block_with_nine_points():
    """knot_payload['v2_direct']['sofr_path'] has 9 points on the quarterly grid."""
    kp = _resolve_then_compose()["knot_payload"]

    assert "v2_direct" in kp, f"expected v2_direct block, got keys {sorted(kp)}"
    assert "supplied" not in kp          # not the supplied path
    v2 = kp["v2_direct"]

    path = v2["sofr_path"]
    assert len(path) == 9, f"expected 9 tenor points, got {len(path)}"
    for i, point in enumerate(path):
        assert isinstance(point, dict) and "time" in point and "value" in point, point
        assert isinstance(point["value"], float), f"point[{i}].value not float: {point['value']!r}"

    assert [p["time"] for p in path] == EXPECTED_SOFR_TIMES


def test_composer_fixed_rates_present_and_derived_from_path():
    """Both swap fixed rates are present, numeric, and follow the discount rule.

    sofr_at(loan_start+0) == sofr_path[0], sofr_at(loan_start+3) == sofr_path[1]
    because the grid points coincide with the swap offsets (0 and 3 months).
    """
    v2 = _resolve_then_compose()["knot_payload"]["v2_direct"]
    path = v2["sofr_path"]

    assert isinstance(v2["swap_now_fixed"], (int, float))
    assert isinstance(v2["swap_later_fixed"], (int, float))

    assert v2["swap_now_fixed"] == _round4(path[0]["value"] - NOW_DISCOUNT)
    assert v2["swap_later_fixed"] == _round4(path[1]["value"] - LATER_DISCOUNT)


def test_composer_provenance_is_domestic_config_file_sourced():
    """Provenance stamp identifies the derived_domestic/v2_direct path + config-file sourcing."""
    kp = _resolve_then_compose()["knot_payload"]
    prov = kp["_provenance"]
    assert prov["mode"] == EXPECTED_MODE
    assert prov["dispatch"] == EXPECTED_DISPATCH
    assert prov["profile_id"] == EXPECTED_PROFILE_ID
    assert prov["profile_mode"] == EXPECTED_MODE
    assert prov["hedge_spec_id"] == "default-3-scenario"
    # Iter-6a stamp wording for the v2_direct derived path cites config_file sourcing.
    assert "config_file" in prov["source_summary"]


def test_composer_audit_records_domestic_dispatch():
    """The composer audit entry surfaces the derived_domestic/v2_direct dispatch."""
    result = _resolve_then_compose()
    entries = result["audit_log"]
    assert len(entries) == 1
    out = entries[0]["output"]
    assert out["mode"] == EXPECTED_MODE
    assert out["dispatch"] == EXPECTED_DISPATCH
    assert out["profile_id"] == EXPECTED_PROFILE_ID
    assert out["sofr_path_points"] == 9
    assert "loan" in out["knot_payload_keys"]
    assert "v2_direct" in out["knot_payload_keys"]


# ══════════════════════════════════════════════════════════════════════
# ITERATION 7 — ecommerce audience (EXTENDS this file per iteration-plan §1)
# ══════════════════════════════════════════════════════════════════════
#
# us-ecommerce.json resolves through the SAME domestic resolver arm + composer
# Branch 3 as us-services, but selects the catalog's 'Ecommerce' column:
#   [base_sofr, demand_volatility, payment_cycle, wc, inventory_carrying]
# inventory_carrying is the overlay-only component appended by the deep-merge;
# payment_cycle is RETAINED (matrix keeps it 'yes' for ecommerce — it is not
# substituted). No _base change, no resolver change (see us-ecommerce.json
# _notes.no_base_change).
#
# SCOPE NOTE — numeric vector NOT frozen here, for two reasons:
#   (1) us-ecommerce.json inputs are flagged ILLUSTRATIVE (same rationale as the
#       Iter-6 services SCOPE NOTE above — don't gate on placeholder values), and
#   (2) the inventory_carrying v1 baseline closed form is now SIGNED OFF (user-
#       confirmed); the fuller CCC form (DIO+DSO−DPO) remains deferred without an
#       architecture change. Reason (2) is therefore resolved — only the illustrative
#       inputs (1) keep the 9-point vector unfrozen. The component unit tests below
#       instead lock the FORM (baseline floor, glut/stockout symmetry), which are
#       robust design properties rather than placeholder magnitudes.

EXPECTED_ECOMMERCE_PROFILE_ID = "us-ecommerce-v1"
EXPECTED_ECOMMERCE_COMPONENTS = [
    "base_sofr", "demand_volatility", "payment_cycle", "wc", "inventory_carrying",
]


def _ecommerce_state() -> dict:
    """public_market_context for the domestic-ecommerce audience.

    Same shape as _domestic_state(); only business_mode + industry change
    (the only two fields the resolver's domestic arm reads).
    """
    return {
        "public_market_context": {
            "business_mode": "domestic_ecommerce",
            "industry": "ecommerce",
            "naics_sector": "454",
            "rate_curve_index": "USD-SOFR-FORWARD",
        },
        "audit_log": [],
    }


def _resolve_then_compose_ecommerce() -> dict:
    profile = profile_resolver_node(_ecommerce_state())["resolved_risk_profile"]
    assert profile is not None
    return composer_node({
        "validated_inputs": SAMPLE_VALIDATED_INPUTS,
        "resolved_risk_profile": profile,
        "resolved_hedge_spec": _load_default_hedge_spec(),
    })


# ── Resolver-level: ecommerce resolves us-ecommerce over _base_domestic ──

def test_ecommerce_resolves_to_us_ecommerce_two_layers():
    """domestic_ecommerce resolves to exactly [us-ecommerce.json, _base_domestic.json]."""
    result = profile_resolver_node(_ecommerce_state())

    assert result.get("validation_errors") is None, result.get("validation_errors")
    assert result["resolved_risk_profile"] is not None
    assert result["risk_factor_profile_id"] == EXPECTED_ECOMMERCE_PROFILE_ID

    paths = result["profile_resolution_path"]
    assert len(paths) == 2, f"expected 2 domestic layers, got {paths}"
    assert "us-ecommerce.json" in paths[0], f"sector layer should be most-specific: {paths}"
    assert "_base_domestic.json" in paths[1], f"base layer should be least-specific: {paths}"


def test_ecommerce_merged_mode_dispatch_and_applies_to():
    """Merged ecommerce profile carries derived_domestic + v2_direct + its applies_to."""
    profile = profile_resolver_node(_ecommerce_state())["resolved_risk_profile"]
    assert profile["mode"] == EXPECTED_MODE
    assert profile["dispatch"] == EXPECTED_DISPATCH
    assert profile["applies_to"] == {"mode": "domestic", "industry": "ecommerce"}


def test_ecommerce_merged_components_retain_payment_cycle_and_append_inventory():
    """Deep-merge keeps the 4-component domestic skeleton (incl. payment_cycle) and
    appends inventory_carrying as the overlay-only 5th component.

    This is the structural assertion of the Iter-7 design decision: inventory_carrying
    is ADDED, payment_cycle is NOT removed (catalog matrix keeps both for ecommerce).
    The order is base-order-then-append because _merge_components builds base_order + extras.
    """
    profile = profile_resolver_node(_ecommerce_state())["resolved_risk_profile"]
    assert _component_names(profile) == EXPECTED_ECOMMERCE_COMPONENTS
    # payment_cycle explicitly retained (guards against a future 'substitution' regression).
    assert "payment_cycle" in _component_names(profile)
    assert "inventory_carrying" in _component_names(profile)


# ── Composer-level: ecommerce Branch 3 builds the SOFR path ──

def test_ecommerce_composer_builds_v2_direct_block_with_nine_points():
    """knot_payload['v2_direct']['sofr_path'] has 9 points on the same quarterly grid."""
    kp = _resolve_then_compose_ecommerce()["knot_payload"]

    assert "v2_direct" in kp, f"expected v2_direct block, got keys {sorted(kp)}"
    assert "supplied" not in kp
    path = kp["v2_direct"]["sofr_path"]
    assert len(path) == 9, f"expected 9 tenor points, got {len(path)}"
    for i, point in enumerate(path):
        assert isinstance(point, dict) and "time" in point and "value" in point, point
        assert isinstance(point["value"], float), f"point[{i}].value not float: {point['value']!r}"
    assert [p["time"] for p in path] == EXPECTED_SOFR_TIMES


def test_ecommerce_composer_fixed_rates_derived_from_path():
    """Both swap fixed rates follow the discount_from_path rule off the ecommerce path."""
    v2 = _resolve_then_compose_ecommerce()["knot_payload"]["v2_direct"]
    path = v2["sofr_path"]
    assert isinstance(v2["swap_now_fixed"], (int, float))
    assert isinstance(v2["swap_later_fixed"], (int, float))
    assert v2["swap_now_fixed"] == _round4(path[0]["value"] - NOW_DISCOUNT)
    assert v2["swap_later_fixed"] == _round4(path[1]["value"] - LATER_DISCOUNT)


def test_ecommerce_composer_provenance_is_domestic_config_file_sourced():
    """Provenance stamp identifies the derived_domestic/v2_direct path for ecommerce."""
    prov = _resolve_then_compose_ecommerce()["knot_payload"]["_provenance"]
    assert prov["mode"] == EXPECTED_MODE
    assert prov["dispatch"] == EXPECTED_DISPATCH
    assert prov["profile_id"] == EXPECTED_ECOMMERCE_PROFILE_ID
    assert prov["profile_mode"] == EXPECTED_MODE
    assert prov["hedge_spec_id"] == "default-3-scenario"
    assert "config_file" in prov["source_summary"]


# ── Component-level: lock the inventory_carrying FORM (not illustrative magnitudes) ──

def test_inventory_carrying_returns_baseline_when_isr_at_mean():
    """Healthy inventory (observed == historic mean) → only the baseline carry, at every t.

    With isr_deviation == 0, peak collapses to baseline, so the trapezoid is flat at
    baseline_bps/10000 across the whole grid.
    """
    from components.inventory_carrying import inventory_carrying_dso_dpo
    inputs = {
        "isr_observed": 1.45,
        "isr_historic_mean": 1.45,
        "sensitivity_bps_per_ratio_point": 200.0,
        "dio_sensitivity": 1.0,
        "baseline_bps": 3.0,
        "stress_timing": {"months_to_peak": 12, "plateau_months": 3, "descent_months": 9},
    }
    for t in (0, 3, 6, 12, 24):
        assert inventory_carrying_dso_dpo(inputs, None, t) == 3.0 / 10000.0


def test_inventory_carrying_glut_and_stockout_are_symmetric():
    """A glut and a stockout of equal |ISR - mean| produce equal stress (abs deviation).

    Locks the catalog-grounded design choice that both directions widen working
    capital (catalog §b.2: 'Both affect working capital').
    """
    from components.inventory_carrying import inventory_carrying_dso_dpo
    base = {
        "isr_historic_mean": 1.45,
        "sensitivity_bps_per_ratio_point": 200.0,
        "dio_sensitivity": 1.0,
        "baseline_bps": 3.0,
        "stress_timing": {"months_to_peak": 12, "plateau_months": 3, "descent_months": 9},
    }
    glut = {**base, "isr_observed": 1.45 + 0.20}     # ISR above mean
    stockout = {**base, "isr_observed": 1.45 - 0.20}  # equal magnitude below mean
    for t in (0, 6, 12, 24):
        assert inventory_carrying_dso_dpo(glut, None, t) == inventory_carrying_dso_dpo(stockout, None, t)


def test_inventory_carrying_peak_matches_documented_formula():
    """At t == months_to_peak the trapezoid is at peak = baseline + dev*sens*dio (in fractions).

    Locks the Iter-7 closed form (v1 baseline SIGNED OFF, user-confirmed): if a future
    move to the fuller CCC form (DIO+DSO−DPO) changes the combination, this expectation
    changes with it — intended.
    """
    from components.inventory_carrying import inventory_carrying_dso_dpo
    inputs = {
        "isr_observed": 1.62,
        "isr_historic_mean": 1.45,
        "sensitivity_bps_per_ratio_point": 200.0,
        "dio_sensitivity": 1.0,
        "baseline_bps": 3.0,
        "stress_timing": {"months_to_peak": 12, "plateau_months": 3, "descent_months": 9},
    }
    dev = abs(1.62 - 1.45)
    expected_peak_bps = 3.0 + dev * 200.0 * 1.0
    assert inventory_carrying_dso_dpo(inputs, None, 12) == expected_peak_bps / 10000.0
