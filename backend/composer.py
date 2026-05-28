"""
composer.py — N3d Composer.

The Composer is the dispatch table that turns
  (validated_inputs, resolved_risk_profile, resolved_hedge_spec)
into a `knot_payload` ready for the Simulation node.

ITERATION-1 SCOPE:
  Supports `mode == "derived"` + `dispatch == "draps_v1"`.
  This is the byte-equality replay path: V2 stamps provenance + builds knot_payload,
  but the actual SOFR derivation runs inside DRAPS (via the inline Postman JS in
  DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json).

  For this dispatch, knot_payload is structurally identical to validated_inputs
  (so the existing simulation_node can be left untouched), with a `_provenance`
  block that records WHICH profile, WHICH hedge spec, and WHY this dispatch path
  was chosen.

ITERATION-3 SCOPE (this iteration):
  Adds `mode == "supplied"` + `dispatch == "draps_v1"`.
  The caller passes `supplied = {sofr_path, swap_now_fixed, swap_later_fixed}` in
  the POST /run body; the intake/request handler lifts that into state['supplied'].
  The composer copies it into knot_payload['supplied'] verbatim — no derivation,
  no defaults, no silent fallback. If state['supplied'] is missing or malformed,
  the composer raises honestly rather than reverting to derivation.

LATER ITERATIONS:
  Iteration 4 adds dispatch=v2_direct (the v2-self-contained SOFR derivation).
  Iteration 5 adds the full N6a Provenance Agent that walks the audit_log and
  enforces I7 (every numeric traceable to a source).
  Iteration 6 adds mode=derived_domestic.

Per design-v1-iteration-plan.md §"ITERATION 1" and §"ITERATION 3", and
design-v1-config-architecture.md §3, §6.

NO LLM IMPORTS — deterministic by design (agent-type law).
"""

from __future__ import annotations

import copy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from components import COMPONENT_REGISTRY

# Required shape of the supplied block. Kept at module scope so tests can import it.
SUPPLIED_REQUIRED_KEYS: tuple[str, ...] = ("sofr_path", "swap_now_fixed", "swap_later_fixed")


def _audit_entry(node: str, summary: str, output: dict[str, Any]) -> dict[str, Any]:
    return {
        "node": node,
        "summary": summary,
        "output": output,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _build_provenance_stamp(
    profile: dict[str, Any],
    spec: dict[str, Any],
    dispatch: str,
    mode: str,
) -> dict[str, Any]:
    """Build the per-run provenance stamp.

    Shallow stamp that records which dispatch path executed and which config
    artifacts drove it. The full I7 invariant (every numeric traceable to a
    source) is enforced separately by the N6a Provenance Agent — Iteration 3
    introduces a minimal version that stamps caller-supplied numbers;
    Iteration 5 makes it complete.

    The `source_summary` is mode-aware so the audit log reads honestly without
    a consumer having to interpret the dispatch/mode pair.
    """
    if mode == "derived" and dispatch == "draps_v1":
        source_summary = (
            "Iteration-1 stamp. SOFR path + swap fixed rates are derived inside "
            "DRAPS by the inline Postman JS in DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json. "
            "V2 composer is a pass-through for this dispatch path."
        )
    elif mode == "supplied" and dispatch == "draps_v1":
        source_summary = (
            "Iteration-3 stamp. SOFR path + swap fixed rates are CALLER-SUPPLIED "
            "via the POST /run 'supplied' block and carried into knot_payload "
            "verbatim. No derivation runs in DRAPS or in V2. The N6a Provenance "
            "Agent (later in the graph) stamps source_type='caller_supplied' on "
            "each supplied numeric."
        )
    elif mode == "derived" and dispatch == "v2_direct":
        source_summary = (
            "Iteration-6a stamp. SOFR path + swap fixed rates are DERIVED IN V2 from the resolved "
            "profile's component formulas (COMPONENT_REGISTRY) and the hedge spec's "
            "discount_from_path rule — no DRAPS roundtrip. The N6a Provenance Agent stamps "
            "source_type='config_file' per SOFR point with per-component attribution."
        )
    else:
        # Defensive: should not be reachable because the dispatch table raises
        # before stamping for unsupported (mode, dispatch) combinations.
        source_summary = f"Stamp for mode={mode!r}, dispatch={dispatch!r}."

    return {
        "schema_version": "1.0.0",
        "stamped_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "dispatch": dispatch,
        "profile_id": profile.get("profile_id"),
        "profile_mode": profile.get("mode"),
        "hedge_spec_id": spec.get("spec_id"),
        "source_summary": source_summary,
    }


def _validate_supplied_block(supplied: Any) -> None:
    """Validate the shape of state['supplied'] for mode='supplied'.

    Raises RuntimeError on ANY shape issue — no silent default, no coercion.
    The caller's authorisation to use these specific numbers is the entire
    contract of supplied mode; if the contract is malformed the composer
    must fail honestly, not paper over it.
    """
    if not isinstance(supplied, dict):
        raise RuntimeError(
            f"composer_node: state['supplied'] must be a dict; "
            f"got {type(supplied).__name__}."
        )

    missing = [k for k in SUPPLIED_REQUIRED_KEYS if k not in supplied]
    if missing:
        raise RuntimeError(
            f"composer_node: state['supplied'] is missing required keys: {missing}. "
            f"Required: {list(SUPPLIED_REQUIRED_KEYS)}. "
            f"Got keys: {sorted(supplied.keys())}."
        )

    sofr_path = supplied["sofr_path"]
    if not isinstance(sofr_path, list) or not sofr_path:
        raise RuntimeError(
            f"composer_node: state['supplied']['sofr_path'] must be a non-empty list; "
            f"got {type(sofr_path).__name__} of length "
            f"{len(sofr_path) if hasattr(sofr_path, '__len__') else 'n/a'}."
        )

    # Each path point must be a dict with time + value, matching V1 SOFR_PATH shape.
    for i, point in enumerate(sofr_path):
        if not isinstance(point, dict):
            raise RuntimeError(
                f"composer_node: state['supplied']['sofr_path'][{i}] must be a dict; "
                f"got {type(point).__name__}."
            )
        if "time" not in point or "value" not in point:
            raise RuntimeError(
                f"composer_node: state['supplied']['sofr_path'][{i}] must have "
                f"'time' and 'value' keys; got {sorted(point.keys())}."
            )
        if not isinstance(point["value"], (int, float)):
            raise RuntimeError(
                f"composer_node: state['supplied']['sofr_path'][{i}]['value'] must be numeric; "
                f"got {type(point['value']).__name__}."
            )

    for k in ("swap_now_fixed", "swap_later_fixed"):
        if not isinstance(supplied[k], (int, float)):
            raise RuntimeError(
                f"composer_node: state['supplied'][{k!r}] must be numeric; "
                f"got {type(supplied[k]).__name__}."
            )


TENOR_POINTS: int = 9
TENOR_STEP_MONTHS: int = 3
V1_COMPONENT_SUM_ORDER: tuple[str, ...] = ("base_sofr", "tariff", "sovereign", "wc")


def _round4(x: float) -> float:
    """Emulate V1 parseFloat(total.toFixed(4)). BYTE-EQUALITY RISK: JS toFixed = half-away-from-zero on
    the shortest decimal repr; Python round = banker's. Decimal(repr).quantize ROUND_HALF_UP matches toFixed
    for the vast majority of cases. D5's v2_direct test is the GATE — if a 4th-decimal mismatch appears,
    revisit this fn (candidate: exact toFixed reimpl) before touching anything else."""
    return float(Decimal(repr(x)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _add_months(d: date, n: int) -> date:
    """JS Date.setMonth overflow semantics (keep day, overflow forward; e.g. Jan31+1mo=Mar3, not clamped)."""
    total = (d.year * 12 + (d.month - 1)) + n
    ty, tm0 = divmod(total, 12)
    return date(ty, tm0 + 1, 1) + timedelta(days=d.day - 1)


def _parse_loan_start(validated: dict) -> date:
    loan = validated.get("loan") or {}
    raw = loan.get("start_date")
    if not raw:
        raise RuntimeError("composer_node (v2_direct): validated_inputs['loan']['start_date'] required to "
                           "anchor the tenor grid but missing/empty.")
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError as exc:
        raise RuntimeError(f"composer_node (v2_direct): could not parse loan start_date {raw!r} as ISO "
                           f"YYYY-MM-DD: {exc}") from exc


def _iso_midnight(d: date) -> str:
    return f"{d.isoformat()}T00:00:00"


def _component_fraction(component: dict, t: int) -> float:
    fid = component.get("formula_id")
    fn = COMPONENT_REGISTRY.get(fid)
    if fn is None:
        raise RuntimeError(f"composer_node (v2_direct): formula_id {fid!r} not in COMPONENT_REGISTRY "
                           f"(known: {sorted(COMPONENT_REGISTRY)}). N3c should have rejected this profile.")
    return fn(component.get("inputs") or {}, component.get("calibration"), t)


def _build_sofr_path(profile: dict, loan_start: date) -> list[dict]:
    by_name = {c.get("name"): c for c in (profile.get("components") or [])}
    missing = [n for n in V1_COMPONENT_SUM_ORDER if n not in by_name]
    if missing:
        raise RuntimeError(f"composer_node (v2_direct): profile missing components {missing}; has {sorted(by_name)}.")
    path: list[dict] = []
    for i in range(TENOR_POINTS):
        t = i * TENOR_STEP_MONTHS
        total = 0.0
        for name in V1_COMPONENT_SUM_ORDER:
            total = total + _component_fraction(by_name[name], t)
        path.append({"time": _iso_midnight(_add_months(loan_start, t)), "value": _round4(total)})
    return path


def _lookup_sofr(sofr_path: list[dict], target: date) -> float:
    for point in sofr_path:
        if date.fromisoformat(point["time"][:10]) >= target:
            return point["value"]
    return sofr_path[-1]["value"]


def _apply_fixed_rate_rule(sofr_path: list[dict], spec: dict, loan_start: date) -> dict:
    rule = spec.get("fixed_rate_rule")
    if rule != "discount_from_path":
        raise NotImplementedError(f"composer_node (v2_direct): fixed_rate_rule={rule!r} unsupported; only "
                                  f"'discount_from_path' implemented.")
    params = spec.get("fixed_rate_params") or {}
    try:
        now_bps = params["swap_now_discount_bps"]; later_bps = params["swap_later_discount_bps"]
    except KeyError as exc:
        raise RuntimeError(f"composer_node (v2_direct): fixed_rate_params missing {exc}; have {sorted(params)}.") from exc
    swap_scn = [s for s in (spec.get("scenarios") or []) if "swap_offset_months" in s]
    swap_scn.sort(key=lambda s: s["swap_offset_months"])
    if len(swap_scn) < 2:
        raise RuntimeError(f"composer_node (v2_direct): expected >=2 swap scenarios w/ swap_offset_months; "
                           f"found {len(swap_scn)}.")
    now_off = swap_scn[0]["swap_offset_months"]; later_off = swap_scn[1]["swap_offset_months"]
    def _fixed(off: int, disc_bps: float) -> float:
        return _round4(_lookup_sofr(sofr_path, _add_months(loan_start, off)) - disc_bps / 10000)
    return {"swap_now_fixed": _fixed(now_off, now_bps), "swap_later_fixed": _fixed(later_off, later_bps)}


def composer_node(state: dict) -> dict:
    """N3d — deterministic. Build knot_payload for the simulation node.

    Dispatch table:
      mode=derived  + dispatch=draps_v1  → Iter-1 pass-through (V1 DRAPS derivation)
      mode=supplied + dispatch=draps_v1  → Iter-3 caller-supplied numbers flow through
      anything else                       → NotImplementedError (honest failure)

    State contract:
      INPUT  state['validated_inputs']       (always required)
             state['resolved_risk_profile']  (always required; sets mode + dispatch)
             state['resolved_hedge_spec']    (always required; identifies hedge spec)
             state['supplied']               (REQUIRED iff mode='supplied'; ignored
                                              otherwise — surfaced via audit summary)

      OUTPUT state['knot_payload']           (composed dict; structure depends on mode)
             state['audit_log']              (one entry appended)
    """
    validated = state.get("validated_inputs")
    profile = state.get("resolved_risk_profile") or {}
    spec = state.get("resolved_hedge_spec") or {}

    if validated is None:
        raise RuntimeError(
            "composer_node called without validated_inputs. "
            "Graph wiring bug — N3 validator must run before N3d composer."
        )

    mode = profile.get("mode")
    dispatch = profile.get("dispatch", "v2_direct")  # default to the V2 destination

    # ── Branch 1: Iter-1 derived path (byte-equality with V1) ───────────────
    if mode == "derived" and dispatch == "draps_v1":
        # Pass-through: knot_payload is a deep copy of validated_inputs with provenance attached.
        # The simulation_node still reads `validated_inputs` (untouched here), so byte-equality
        # with V1 is preserved.
        knot_payload = copy.deepcopy(validated)
        knot_payload["_provenance"] = _build_provenance_stamp(profile, spec, dispatch, mode=mode)

        summary = (
            f"composed knot_payload (mode={mode}, dispatch={dispatch}, "
            f"profile={profile.get('profile_id')}, spec={spec.get('spec_id')})"
        )

        return {
            "knot_payload": knot_payload,
            "audit_log": [
                _audit_entry(
                    "composer",
                    summary,
                    {
                        "mode": mode,
                        "dispatch": dispatch,
                        "profile_id": profile.get("profile_id"),
                        "spec_id": spec.get("spec_id"),
                        "knot_payload_keys": sorted(knot_payload.keys()),
                    },
                )
            ],
        }

    # ── Branch 2: Iter-3 supplied path (caller passes SOFR + fixed rates) ───
    if mode == "supplied" and dispatch == "draps_v1":
        supplied = state.get("supplied")
        if supplied is None:
            raise RuntimeError(
                "composer_node: profile.mode='supplied' but state['supplied'] is missing. "
                "The request handler (POST /run) must lift the body's 'supplied' field "
                "into state['supplied'] when supplied mode is selected. Refusing to "
                "silently derive a SOFR path the caller did not authorize."
            )
        _validate_supplied_block(supplied)

        knot_payload = copy.deepcopy(validated)
        knot_payload["supplied"] = copy.deepcopy(supplied)
        knot_payload["_provenance"] = _build_provenance_stamp(profile, spec, dispatch, mode=mode)

        summary = (
            f"composed knot_payload (mode={mode}, dispatch={dispatch}, "
            f"profile={profile.get('profile_id')}, spec={spec.get('spec_id')}, "
            f"sofr_path_points={len(supplied['sofr_path'])})"
        )

        return {
            "knot_payload": knot_payload,
            "audit_log": [
                _audit_entry(
                    "composer",
                    summary,
                    {
                        "mode": mode,
                        "dispatch": dispatch,
                        "profile_id": profile.get("profile_id"),
                        "spec_id": spec.get("spec_id"),
                        "knot_payload_keys": sorted(knot_payload.keys()),
                        "supplied_sofr_path_points": len(supplied["sofr_path"]),
                        "supplied_swap_now_fixed": supplied["swap_now_fixed"],
                        "supplied_swap_later_fixed": supplied["swap_later_fixed"],
                    },
                )
            ],
        }

    # ── Branch 3: Iter-6a derived path (v2_direct — V2 computes SOFR itself) ─
    if mode == "derived" and dispatch == "v2_direct":
        components = profile.get("components")
        if not components:
            raise RuntimeError("composer_node: mode='derived' dispatch='v2_direct' but the resolved profile "
                               "carries no components[] to derive the SOFR path from.")
        loan_start = _parse_loan_start(validated)
        sofr_path = _build_sofr_path(profile, loan_start)
        fixed = _apply_fixed_rate_rule(sofr_path, spec, loan_start)
        knot_payload = copy.deepcopy(validated)
        knot_payload["v2_direct"] = {"sofr_path": sofr_path,
                                     "swap_now_fixed": fixed["swap_now_fixed"],
                                     "swap_later_fixed": fixed["swap_later_fixed"]}
        knot_payload["_provenance"] = _build_provenance_stamp(profile, spec, dispatch, mode=mode)
        summary = (f"composed knot_payload (mode={mode}, dispatch={dispatch}, "
                   f"profile={profile.get('profile_id')}, spec={spec.get('spec_id')}, "
                   f"sofr_path_points={len(sofr_path)})")
        return {"knot_payload": knot_payload,
                "audit_log": [_audit_entry("composer", summary,
                    {"mode": mode, "dispatch": dispatch, "profile_id": profile.get("profile_id"),
                     "spec_id": spec.get("spec_id"), "knot_payload_keys": sorted(knot_payload.keys()),
                     "sofr_path_points": len(sofr_path),
                     "swap_now_fixed": fixed["swap_now_fixed"], "swap_later_fixed": fixed["swap_later_fixed"]})]}

    # ── Honest failure for any unsupported (mode, dispatch) combination ─────
    raise NotImplementedError(
        f"Composer supports:\n"
        f"  mode='derived'  + dispatch='draps_v1'   (Iteration 1)\n"
        f"  mode='supplied' + dispatch='draps_v1'   (Iteration 3)\n"
        f"  mode='derived'  + dispatch='v2_direct'  (Iteration 6a)\n"
        f"Got mode={mode!r}, dispatch={dispatch!r}.\n"
        f"mode='derived_domestic' lands in a later iteration."
    )
