"""
profile_resolver.py \u2014 N3a Profile Resolver.

ITERATION-2 IMPLEMENTATION. Real candidate-list + deep-merge layered resolver
per design-v1-config-architecture.md \u00a74.

ALGORITHM
=========
1. Derive business_identity from state.public_market_context.
2. Walk config/risk-factor-profiles/{mode-as-hyphenated-dir}/*.json, classifying
   each file by its `applies_to` block into one of three layers:
     - commodity : applies_to matches mode + exporter + importer + commodity_gtap.
     - corridor  : applies_to matches mode + exporter + importer; commodity_gtap absent.
     - base      : applies_to has only mode; exporter/importer/commodity_gtap absent.
   Each layer must contain AT MOST one matching file. Multiple matches = config drift
   and routes to give_up via validation_errors.
3. Build candidates list (most-specific first): [commodity, corridor, base].
   Missing layers are skipped (commodity-only profiles, or base-only fallback are valid
   shapes; the only hard requirement is at least one layer matches).
4. Deep-merge in REVERSE order \u2014 base first, then corridor, then commodity \u2014 so
   the most-specific layer wins on scalar conflicts.
5. The `components` array merges by `name`:
     - components present in both: deep-merge their dicts (more-specific wins).
     - components only in more-specific: append in overlay order.
     - components only in more-general: preserved in base order.
6. Record profile_resolution_path = the relative paths of files actually merged
   (most-specific first \u2014 the candidate order, not the merge order).
7. If candidates is empty OR any scan-level error occurred (duplicate layer files,
   bad JSON, missing directory), surface validation_errors and return a None profile.

The post-N3c conditional edge (deliverable 5) routes failures here to give_up.
This node never raises on a recoverable error; it surfaces honest errors instead.

CONTRACT
========
  Reads  state.public_market_context
           export_import: corridor.origin / corridor.destination / gtap_commodity_code
           domestic:      business_mode / industry  (naics_sector also carried in context)
  Writes state.business_identity
         state.risk_factor_profile_id
         state.resolved_risk_profile
         state.profile_resolution_path
         state.validation_errors           (only on failure)
         state.audit_log                   (always; one entry)

NO LLM IMPORTS \u2014 deterministic by design (agent-type law).
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_sources.api_binding import bind_api_sources


def _fred_api_key() -> str:
    """Read the FRED key from settings lazily.

    Imported inside the function (not at module top) so this deterministic node
    has no import-time dependency on a populated environment: offline/CI runs
    that never bind an api-sourced component must not fail merely because
    config import side-effects run. settings.fred_api_key defaults to '' when
    unset; bind_api_sources turns a blank key into an honest FRED failure only
    for profiles that actually declare source.type=='api'.
    """
    from config import settings
    return getattr(settings, "fred_api_key", "") or ""


_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent
_PROFILES_ROOT = _REPO_ROOT / "config" / "risk-factor-profiles"


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Helpers
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def _audit_entry(node: str, summary: str, output: dict[str, Any]) -> dict[str, Any]:
    return {
        "node": node,
        "summary": summary,
        "output": output,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _derive_business_identity(public_market_context: dict | None) -> dict:
    """Translate N2 market-context into the canonical business_identity shape.

    Iteration 2: only export_import is supported by downstream nodes. Domestic
    profiles (mode='domestic') are scaffolded in the file layout but no leaf
    files exist yet \u2014 the resolver still scans /domestic/ if asked.
    """
    ctx = public_market_context or {}
    mode = ctx.get("business_mode") or "export_import"
    if mode == "export_import":
        corridor = ctx.get("corridor") or {}
        return {
            "mode": "export_import",
            "exporter": corridor.get("origin"),
            "importer": corridor.get("destination"),
            "commodity_gtap": ctx.get("gtap_commodity_code"),
        }
    # Domestic fine modes (domestic_services Iter-6; domestic_ecommerce Iter-7).
    # Coarse audience match happens in _classify via applies_to.industry.
    return {"mode": mode, "industry": ctx.get("industry")}


def _mode_to_dirname(mode: str | None) -> str:
    """Map state mode (snake_case enum) to filesystem directory (hyphenated).

    Domestic fine modes (domestic_services, domestic_ecommerce) all live under the
    single coarse 'domestic/' directory — the sector is disambiguated by
    applies_to.industry inside the files, not by directory.
    """
    if (mode or "").startswith("domestic"):
        return "domestic"
    return (mode or "").replace("_", "-")


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Deep merge \u2014 the heart of \u00a74
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def deep_merge(base: Any, overlay: Any) -> Any:
    """Recursively merge `overlay` onto `base`. Overlay wins on scalar conflicts.

    Rules:
      - Both dicts: recurse per key.
      - Both lists AND the key is `components` (handled by the parent dict-merge
        case): use _merge_components.
      - Otherwise: overlay replaces.
    Inputs are never mutated; the return value is a deep copy.
    """
    if isinstance(base, dict) and isinstance(overlay, dict):
        out = copy.deepcopy(base)
        for k, v in overlay.items():
            if k == "components" and isinstance(v, list) and isinstance(out.get(k), list):
                out[k] = _merge_components(out[k], v)
            elif isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = deep_merge(out[k], v)
            else:
                out[k] = copy.deepcopy(v)
        return out
    return copy.deepcopy(overlay)


def _merge_components(base_components: list[dict], overlay_components: list[dict]) -> list[dict]:
    """Merge two component-arrays by `name`.

    Components present in both \u2192 deep_merge (overlay wins on scalar conflicts).
    Components only in overlay \u2192 appended in overlay order.
    Components only in base    \u2192 preserved in base order.
    """
    by_name: dict[str, dict] = {}
    base_order: list[str] = []
    for c in base_components:
        name = c.get("name")
        if not name:
            continue
        by_name[name] = copy.deepcopy(c)
        base_order.append(name)

    extras: list[str] = []
    for c in overlay_components:
        name = c.get("name")
        if not name:
            continue
        if name in by_name:
            by_name[name] = deep_merge(by_name[name], c)
        else:
            by_name[name] = copy.deepcopy(c)
            extras.append(name)

    return [by_name[n] for n in (base_order + extras)]


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Candidate discovery
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def _classify(applies_to: dict, identity: dict) -> str | None:
    """Return the layer this file belongs to for `identity`, or None if no match.

    Strict shape per layer:
      base       : applies_to has mode (matching) and NOTHING ELSE relevant.
      corridor   : applies_to has mode + exporter + importer (all matching);
                   commodity_gtap absent.
      commodity  : applies_to has mode + exporter + importer + commodity_gtap (all matching).

    `mode` must always be explicit in applies_to. Files in a directory have no
    implicit mode \u2014 the content is the truth (avoids path/content coupling).
    """
    identity_mode = identity.get("mode") or ""

    if identity_mode.startswith("domestic"):
        if applies_to.get("mode") != "domestic":
            return None
        industry = applies_to.get("industry")
        if industry is None:
            return "base"                        # _base_domestic.json
        if industry == identity.get("industry"):
            return "sector"                      # us-services.json
        return None

    # export-import arm (unchanged below)
    if applies_to.get("mode") != identity_mode:
        return None

    exp = applies_to.get("exporter")
    imp = applies_to.get("importer")
    com = applies_to.get("commodity_gtap")

    # base: only mode is set
    if exp is None and imp is None and com is None:
        return "base"

    # corridor: mode + exporter + importer match, no commodity
    if (
        exp == identity.get("exporter")
        and imp == identity.get("importer")
        and com is None
    ):
        return "corridor"

    # commodity: mode + exporter + importer + commodity all match
    if (
        exp == identity.get("exporter")
        and imp == identity.get("importer")
        and com == identity.get("commodity_gtap")
    ):
        return "commodity"

    return None


def _scan_candidates(identity: dict) -> tuple[list[Path], list[str]]:
    """Return (candidate paths most-specific first, list of scan errors).

    Errors include: directory missing, files with bad JSON, multiple files
    matching a single layer (= ambiguous config). Missing layers are NOT
    errors here; the caller decides whether the resulting candidate list is
    empty enough to give up.
    """
    errors: list[str] = []
    mode_dir = _PROFILES_ROOT / _mode_to_dirname(identity.get("mode"))

    if not mode_dir.is_dir():
        rel = (
            mode_dir.relative_to(_REPO_ROOT)
            if _REPO_ROOT in mode_dir.parents
            else mode_dir
        )
        errors.append(f"profile_resolver: profiles directory not found: {rel}")
        return [], errors

    buckets: dict[str, list[Path]] = {"commodity": [], "corridor": [], "sector": [], "base": []}
    for path in sorted(mode_dir.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            errors.append(
                f"profile_resolver: failed to read {path.relative_to(_REPO_ROOT)}: {e}"
            )
            continue
        applies = data.get("applies_to") or {}
        layer = _classify(applies, identity)
        if layer is not None:
            buckets[layer].append(path)

    for layer, paths in buckets.items():
        if len(paths) > 1:
            rels = ", ".join(str(p.relative_to(_REPO_ROOT)) for p in paths)
            errors.append(
                f"profile_resolver: layer '{layer}' has {len(paths)} matching files "
                f"for identity {identity}: {rels}. Expected exactly one."
            )

    # Most-specific first. Skip empty layers. Layer set + "specific" definition
    # are mode-aware: export-import uses commodity/corridor; domestic uses sector.
    is_domestic = (identity.get("mode") or "").startswith("domestic")
    if is_domestic:
        layer_order = ("sector", "base")
    else:
        layer_order = ("commodity", "corridor", "base")
    candidates: list[Path] = [buckets[l][0] for l in layer_order if buckets[l]]

    # Design rule: _base.json is "defaults; never used alone"
    # (design-v1-config-architecture.md §2). Require at least one specific layer
    # (commodity OR corridor) to match. A base-only match means the identity
    # didn't actually match any concrete profile — surface that as no-match
    # rather than silently shipping a defaults-only profile.
    if is_domestic:
        has_specific_layer = bool(buckets["sector"])
    else:
        has_specific_layer = bool(buckets["commodity"]) or bool(buckets["corridor"])
    if candidates and not has_specific_layer:
        candidates = []

    return candidates, errors


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Node entry point
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def _synthesize_caller_supplied_profile(supplied: dict) -> dict:
    """Build a synthesized risk-factor profile for mode='supplied' runs.

    Iteration-3 deliverable 4b. When state['supplied'] is present, the resolver
    skips the disk-based candidate-list scan and instead returns a minimal,
    fully-valid profile that selects (mode='supplied', dispatch='draps_v1') for
    the composer to route on.

    The profile carries a `supplied` block translated from state['supplied'] so
    that N3c profile_spec_validator's mode-invariant + JSON Schema checks find
    what they need. NOTE the key-name translation:

        state['supplied']['swap_now_fixed']    -> profile.supplied.swap_now_fixed_rate
        state['supplied']['swap_later_fixed']  -> profile.supplied.swap_later_fixed_rate

    The two naming conventions are an existing inconsistency in the codebase
    (state-level uses short names; profile schema uses '_rate'-suffixed names).
    This synthesis bridges them rather than touching either side. The composer
    (N3d) reads state['supplied'] verbatim -- NOT profile.supplied -- so the
    composer's _validate_supplied_block remains the authoritative gate for the
    caller-supplied data on the knot payload. The duplication is intentional:
    profile.supplied exists for validator contract; state['supplied'] flows
    into knot_payload.

    Defensive on missing keys: uses .get() so a malformed supplied block
    produces a profile that the downstream schema/invariant checks will reject
    honestly, rather than crashing this synthesizer with a KeyError. The
    composer's _validate_supplied_block is the strict gate; this helper does
    not duplicate that validation.
    """
    sofr_path_in = supplied.get("sofr_path") or []
    return {
        "profile_id":    "caller_supplied",
        "version":       "1.0.0",
        "mode":          "supplied",
        "dispatch":      "draps_v1",
        "hedge_spec_id": "supplied-rates-example",
        "supplied": {
            "sofr_path": [
                {"time": p.get("time"), "value": p.get("value")}
                for p in sofr_path_in
                if isinstance(p, dict)
            ],
            "swap_now_fixed_rate":   supplied.get("swap_now_fixed"),
            "swap_later_fixed_rate": supplied.get("swap_later_fixed"),
        },
    }


def profile_resolver_node(state: dict) -> dict:
    """N3a \u2014 deterministic. Resolve a layered risk-factor profile from business identity.

    Iteration 2: real candidate-list + deep-merge implementation per \u00a74.
    """
    identity = _derive_business_identity(state.get("public_market_context"))

    # Iter-3 deliverable 4b: short-circuit for caller-supplied mode.
    # If the request handler lifted a 'supplied' block into state, skip the
    # disk-based candidate-list scan and synthesize a minimal profile that
    # selects (mode='supplied', dispatch='draps_v1'). The composer reads
    # state['supplied'] verbatim; the synthesized profile.supplied block is
    # shaped (with '_rate'-suffixed keys) to satisfy N3c's mode-invariant and
    # JSON Schema checks. business_identity is still derived from market_context
    # so the audit log retains the corridor/commodity snapshot even on the
    # supplied path.
    supplied = state.get("supplied")
    if supplied is not None:
        synthesized = _synthesize_caller_supplied_profile(supplied)
        return {
            "business_identity": identity,
            "risk_factor_profile_id": synthesized["profile_id"],
            "resolved_risk_profile": synthesized,
            "profile_resolution_path": ["<synthesized: caller_supplied>"],
            "audit_log": [
                _audit_entry(
                    "profile_resolver",
                    "synthesized supplied-mode profile (disk-based candidate scan skipped)",
                    {
                        "profile_id":     synthesized["profile_id"],
                        "mode":           synthesized["mode"],
                        "dispatch":       synthesized["dispatch"],
                        "hedge_spec_id":  synthesized["hedge_spec_id"],
                        "identity":       identity,
                        "synthesis_marker": "caller_supplied",
                    },
                )
            ],
        }

    candidates, scan_errors = _scan_candidates(identity)

    # Failure path: no candidates OR scan-level errors. Surface honest errors
    # and return a None profile. The post-N3c router (deliverable 5) sends
    # this to give_up.
    if scan_errors or not candidates:
        errors = list(scan_errors)
        if not candidates:
            mode_dir_rel = (
                _PROFILES_ROOT.relative_to(_REPO_ROOT)
                / _mode_to_dirname(identity.get("mode"))
            )
            errors.append(
                f"profile_resolver: no profile matches business identity {identity}. "
                f"Searched {mode_dir_rel}/. Need at least one specific layer to match: "
                "a commodity leaf (applies_to matching mode+exporter+importer+commodity_gtap) "
                "OR a corridor file (applies_to matching mode+exporter+importer). "
                "_base.json contributes defaults but per design-v1-config-architecture.md §2 "
                "is never used alone."
            )
        return {
            "business_identity": identity,
            "risk_factor_profile_id": None,
            "resolved_risk_profile": None,
            "profile_resolution_path": [],
            "validation_errors": errors,
            "audit_log": [
                _audit_entry(
                    "profile_resolver",
                    f"\u2717 resolution failed: {len(errors)} error(s)",
                    {"identity": identity, "errors": errors},
                )
            ],
        }

    # Success: deep-merge in REVERSE order \u2014 base first, then progressively more
    # specific \u2014 so most-specific wins on scalar conflicts.
    merged: dict = {}
    for path in reversed(candidates):
        with path.open("r", encoding="utf-8") as f:
            layer = json.load(f)
        merged = deep_merge(merged, layer)

    resolution_path = [str(p.relative_to(_REPO_ROOT)) for p in candidates]
    profile_id = merged.get("profile_id", "unknown")

    # Iter-8: live-data binding (Option A). After the layered merge, resolve any
    # component whose source.type=='api' to a live value (FRED SOFR for the
    # base_sofr 'initial' input) BEFORE the composer runs. On outage with no
    # profile-authorised cache fallback, bind_api_sources returns errors; we
    # surface them as validation_errors so the EXISTING post-N3c conditional
    # edge routes to GIVE-UP. graph.py and composer.py wiring stay unchanged.
    # Profiles with no api-sourced component (the Iter-1..7 config_file/snapshot
    # profiles) pass through bind_api_sources untouched and never touch the
    # network, so offline/CI runs are unaffected.
    needs_key = any((c.get("source") or {}).get("type") == "api"
                    for c in (merged.get("components") or []))
    bound, bind_errors = bind_api_sources(merged, api_key=_fred_api_key() if needs_key else "")
    if bind_errors:
        return {
            "business_identity": identity,
            "risk_factor_profile_id": profile_id,
            "resolved_risk_profile": None,
            "profile_resolution_path": resolution_path,
            "validation_errors": bind_errors,
            "audit_log": [
                _audit_entry(
                    "profile_resolver",
                    f"\u2717 api binding failed: {len(bind_errors)} error(s)",
                    {
                        "profile_id": profile_id,
                        "resolution_path": resolution_path,
                        "identity": identity,
                        "errors": bind_errors,
                    },
                )
            ],
        }
    merged = bound

    # Surface the api binding outcome (if any) in the audit entry so the trace
    # shows live-vs-stale provenance at the resolver boundary.
    api_binding_summary = [
        {
            "component": c.get("name"),
            "binding_result": (c.get("source") or {}).get("binding_result"),
        }
        for c in (merged.get("components") or [])
        if (c.get("source") or {}).get("binding_result") is not None
    ]

    return {
        "business_identity": identity,
        "risk_factor_profile_id": profile_id,
        "resolved_risk_profile": merged,
        "profile_resolution_path": resolution_path,
        "audit_log": [
            _audit_entry(
                "profile_resolver",
                f"\u2713 merged profile {profile_id} from {len(candidates)} layer(s)"
                + (f"; api-bound {len(api_binding_summary)} component(s)" if api_binding_summary else ""),
                {
                    "profile_id": profile_id,
                    "resolution_path": resolution_path,
                    "identity": identity,
                    "api_bindings": api_binding_summary,
                },
            )
        ],
    }
