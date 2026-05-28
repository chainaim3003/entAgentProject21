"""
test_no_silent_default.py — Iteration 4 deliverable.

Sentinel tests for the architectural commitment in
design-v1-iteration-plan.md §0: "No silent fallbacks, no hardcoding, no mocks.
Honest failure is preferred to a wrong answer."

This file targets the most tempting "silent default" risk surfaces:

  • Resolver-level:
      1. Unknown corridor → no profile + validation_errors, NOT a silent fallback
         to some default corridor.
      2. Unknown corridor + known commodity → still no profile (the textile leaf
         alone is NOT a valid dispatch; corridor identity must match).
      3. Known corridor + unknown commodity → corridor+base only; the resolver
         must NOT silently synthesize a commodity leaf.

  • Composer-level:
      4. mode='derived' without a dispatch field → composer defaults to v2_direct
         per its own code. As of Iter-6a the v2_direct branch is implemented, so
         an absent dispatch must ENTER that branch (and fail honestly on this
         component-less test profile), NOT silently fall back to draps_v1.
      5. mode='derived' + dispatch='v2_direct' explicitly → same: enters the
         v2_direct branch and raises an honest RuntimeError on the missing
         components, rather than falling back to draps_v1.
      6. Unknown mode → NotImplementedError. The composer must NOT silently route
         to the closest supported mode.

  • Validator-level:
      7. mode='derived' + supplied block present → validation_errors. The
         validator must NOT silently strip the supplied block to make the profile
         "look" derived.

Each test names the silent-default risk it forecloses in the docstring so future
contributors can see what would break if they relax the check.

NO live services required — pure file I/O + Python. Safe to run in CI.

RUN:
    cd backend
    .venv\\Scripts\\activate
    pytest tests/test_no_silent_default.py -v
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
from profile_spec_validator import profile_spec_validator_node  # noqa: E402


# Shared minimal state-builders -----------------------------------------------

def _state_for(exporter: str | None, importer: str | None, commodity: str | None) -> dict:
    return {
        "public_market_context": {
            "corridor": {"origin": exporter, "destination": importer},
            "gtap_commodity_code": commodity,
        },
        "audit_log": [],
    }


SAMPLE_VALIDATED_INPUTS = {
    "loan": {
        "notional_usd": 1_000_000.0,
        "spread_bps": 250.0,
        "term_months": 24,
        "start_date": "2026-03-01",
    },
    "market": {"gtap_commodity_code": "tex"},
}

SAMPLE_HEDGE_SPEC = {"spec_id": "default-3-scenario"}


# ──────────────────────────────────────────────────────────────────────
# RESOLVER: no silent fallback to a default corridor
# ──────────────────────────────────────────────────────────────────────

def test_unknown_corridor_returns_errors_not_silent_fallback():
    """ZZ-XX identity must NOT silently dispatch india-us-textiles or vietnam-us-textiles.

    SILENT-DEFAULT RISK FORECLOSED: a future "convenience fallback" that picks
    "the closest" corridor when none matches would mask configuration bugs and
    produce hedge recommendations for the wrong country. The resolver must
    return None profile + an explicit validation_error.
    """
    result = profile_resolver_node(_state_for("ZZ", "XX", "tex"))

    assert result["resolved_risk_profile"]   is None
    assert result["risk_factor_profile_id"]  is None
    assert result["profile_resolution_path"] == []
    errors = result.get("validation_errors") or []
    assert any("no profile matches" in e for e in errors), (
        f"expected 'no profile matches' error; got {errors}"
    )


def test_unknown_corridor_with_textile_commodity_still_returns_errors():
    """Even with a KNOWN commodity (tex), an UNKNOWN corridor must NOT dispatch.

    SILENT-DEFAULT RISK FORECLOSED: a future "commodity-driven" shortcut that
    falls back to any X-US-tex leaf when corridor is unknown would route a
    Bangladesh exporter (BD-US-tex) through India's sovereign spread. The
    commodity match alone is insufficient — the FULL identity must match a
    specific corridor layer.
    """
    result = profile_resolver_node(_state_for("BD", "US", "tex"))

    assert result["resolved_risk_profile"] is None
    errors = result.get("validation_errors") or []
    assert any("no profile matches" in e for e in errors), errors


def test_known_corridor_with_unknown_commodity_does_not_synthesize_leaf():
    """VN-US-rice resolves to corridor+base only (no commodity leaf synthesized).

    SILENT-DEFAULT RISK FORECLOSED: a future "use the closest commodity" shortcut
    that picks vietnam-us-textiles.json for a rice query would produce a hedge
    recommendation with textile-DSO WC stress applied to a rice loan. The
    resolver must surface partial matches honestly (2 layers, not 3) so the
    downstream validator can decide whether the partial profile is dispatchable.
    """
    result = profile_resolver_node(_state_for("VN", "US", "rice"))

    paths = result["profile_resolution_path"]
    assert len(paths) == 2, f"expected corridor+base only; got {paths}"
    assert "vietnam-us.json" in paths[0]
    assert "_base.json"      in paths[1]
    # Crucially, the textile leaf must NOT have been picked up.
    for p in paths:
        assert "textiles" not in p, f"textile leaf silently synthesized: {p}"


# ──────────────────────────────────────────────────────────────────────
# COMPOSER: no silent fallback to draps_v1 when dispatch is wrong/missing
# ──────────────────────────────────────────────────────────────────────

def _composer_state_with(profile_overrides: dict) -> dict:
    base_profile = {
        "profile_id": "test-derived-profile",
        "mode": "derived",
        # NOTE: dispatch deliberately left out by some callers below.
    }
    base_profile.update(profile_overrides)
    return {
        "validated_inputs": SAMPLE_VALIDATED_INPUTS,
        "resolved_risk_profile": base_profile,
        "resolved_hedge_spec":   SAMPLE_HEDGE_SPEC,
    }


def test_composer_default_dispatch_v2_direct_raises_not_silent_fallback():
    """Profile with mode='derived' and NO dispatch field defaults to v2_direct in
    composer.py (`dispatch = profile.get("dispatch", "v2_direct")`). As of Iter-6a
    the v2_direct branch is IMPLEMENTED, so an absent dispatch must ENTER that
    branch — not silently fall back to draps_v1.

    SILENT-DEFAULT RISK FORECLOSED: defaulting an absent dispatch to draps_v1
    "to be safe" would silently route a profile written for the v2-direct path
    through DRAPS via a deep-copy pass-through — which would SUCCEED and produce
    wrong numbers with no error. Here the profile carries no components[], so the
    v2_direct branch fails honestly with a RuntimeError naming v2_direct and the
    missing components; a draps_v1 fallback would have returned a knot_payload
    instead of raising.

    NOTE: NotImplementedError is a subclass of RuntimeError, so the message
    assertions below — not the exception type alone — are what prove the
    v2_direct branch was entered rather than the final NotImplemented dispatch-
    table error, whose text contains 'v2_direct' but NOT 'component'.
    """
    state = _composer_state_with({})  # mode=derived, no dispatch → defaults to v2_direct
    with pytest.raises(RuntimeError) as exc:
        composer_node(state)
    msg = str(exc.value)
    # Both words together prove the Branch-3 honest failure (the dispatch-table
    # NotImplementedError has 'v2_direct' but no 'component'; a draps_v1 fallback
    # would not have raised at all).
    assert "v2_direct" in msg
    assert "component" in msg


def test_composer_explicit_v2_direct_raises_not_silent_fallback():
    """Explicit dispatch='v2_direct' on a derived profile must ENTER the v2_direct
    branch (implemented in Iter-6a), not silently fall back to draps_v1.

    SILENT-DEFAULT RISK FORECLOSED: a future "if v2_direct can't complete, use
    draps_v1" convenience would mask the fact that the author asked for v2_direct.
    Here the profile carries no components[], so the branch fails honestly with a
    RuntimeError naming v2_direct and the missing components; a draps_v1 fallback
    would have returned a knot_payload instead of raising.
    """
    state = _composer_state_with({"dispatch": "v2_direct"})
    with pytest.raises(RuntimeError) as exc:
        composer_node(state)
    msg = str(exc.value)
    assert "v2_direct" in msg
    assert "component" in msg


def test_composer_unknown_mode_raises_no_silent_default():
    """A profile with mode='made_up' must NOT route to the closest supported mode.

    SILENT-DEFAULT RISK FORECLOSED: defaulting an unknown mode to 'derived' would
    silently process a future mode (e.g. derived_domestic with a typo) through
    the export-import dispatch table.
    """
    state = _composer_state_with({"mode": "made_up", "dispatch": "draps_v1"})
    with pytest.raises(NotImplementedError) as exc:
        composer_node(state)
    msg = str(exc.value)
    # The error must list the supported combinations explicitly.
    assert "derived" in msg
    assert "supplied" in msg


# ──────────────────────────────────────────────────────────────────────
# VALIDATOR: no silent acceptance of mode/contents contradictions
# ──────────────────────────────────────────────────────────────────────

def test_validator_rejects_supplied_block_in_derived_mode_no_silent_acceptance():
    """mode='derived' with a supplied block present must produce a validation
    error from N3c's mode_invariants check. The validator must NOT silently
    strip the supplied block to make the profile "look" derived.

    SILENT-DEFAULT RISK FORECLOSED: a future "auto-clean the supplied block"
    convenience in the validator would let a profile that's confused about its
    own mode silently dispatch as derived, while a downstream consumer might
    still see the supplied block on the profile object and dispatch differently.
    """
    bad_profile = {
        "profile_id": "confused-profile",
        "version":    "1.0.0",
        "mode":       "derived",
        "dispatch":   "draps_v1",
        "components": [
            {"name": "base_sofr", "formula_id": "base_sofr_fed_path_linear",
             "inputs": {"initial": 0.045, "peak": 0.055, "final": 0.0475,
                        "months_to_peak": 12, "total_months_assumption": 24}},
        ],
        # The contradiction: a 'supplied' block on a derived profile.
        "supplied": {
            "sofr_path": [{"time": "2026-02-28T00:00:00", "value": 0.06}],
            "swap_now_fixed_rate":   0.05,
            "swap_later_fixed_rate": 0.058,
        },
    }
    state = {
        "resolved_risk_profile": bad_profile,
        "resolved_hedge_spec": {
            "spec_id": "default-3-scenario",
            "version": "1.0.0",
            "scenarios": [
                {"id": "A", "kind": "no_hedge"},
                {"id": "B", "kind": "swap_now",   "swap_discount_bps": 100},
                {"id": "C", "kind": "swap_later", "swap_discount_bps":  70,
                 "swap_later_offset_months": 3},
            ],
        },
        "audit_log": [],
    }

    result = profile_spec_validator_node(state)
    errors = result.get("validation_errors") or []
    assert errors, "validator must NOT silently accept derived + supplied"
    # The mode_invariants check labels its errors with the 'mode invariant' prefix.
    assert any("mode invariant" in e and "supplied" in e for e in errors), (
        f"expected mode_invariant error naming 'supplied'; got {errors}"
    )
