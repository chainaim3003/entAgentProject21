"""
deterministic_agents.py — N3, N4, N6, N8, NX  (NO Gemini, by design).

THIS FILE CONTAINS NO LLM IMPORTS.
The agent-type law (DESIGN/DESIGN1/design-1-conceptual-design.md) is enforced here by
the import list at the top of this module. `grep import deterministic_agents.py` is the audit.

Nodes:
  N3  Input-Validator  — schema check; the boundary
  N4  Simulation       — THE KNOT; wraps DRAPS run_simulation
  N6  Disclosure       — wraps ACTUS-Mentor /generate-xbrl-report
  N8  Memory           — persistence (predicted-vs-realised loop)
  NX  Give-Up          — honest termination, never fabricates a result

References:
  • DESIGN/DESIGN1/design-1-detailed-design.md §1 (textual graph)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# ONLY deterministic imports below. Adding google.generativeai here would break the design.
import actus_client
import actus_mentor_client
import draps_client
import memory_store


# ───────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────

def _audit_entry(node: str, summary: str, output: dict[str, Any]) -> dict[str, Any]:
    return {
        "node": node,
        "summary": summary,
        "output": output,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _is_finite_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ───────────────────────────────────────────────────────────────────────
# N3 — INPUT-VALIDATOR  (THE BOUNDARY)
# ───────────────────────────────────────────────────────────────────────

def validator_node(state: dict) -> dict:
    """N3 — deterministic. Schema-check everything from the wings.

    Produces `validated_inputs` ONLY when all checks pass.
    On failure, produces `validation_errors` (non-empty) so the conditional edge
    can route to retry or give-up.

    Nothing schema-dirty crosses this boundary. No LLM involved. Pure rules.
    """
    raw = state.get("raw_inputs") or {}
    ctx = state.get("public_market_context") or {}
    errors: list[str] = []

    # Required fields from intake
    notional = raw.get("notional_usd")
    spread = raw.get("spread_bps")
    term = raw.get("term_months")
    start_date = raw.get("start_date")
    rate_index = raw.get("rate_index")

    if not _is_finite_number(notional):
        errors.append("raw_inputs.notional_usd: must be a number")
    elif notional <= 0:
        errors.append("raw_inputs.notional_usd: must be > 0")
    elif notional > 1_000_000_000:
        errors.append("raw_inputs.notional_usd: implausibly large (>1B); recheck units")

    if not _is_finite_number(spread):
        errors.append("raw_inputs.spread_bps: must be a number")
    elif spread < 0 or spread > 5000:
        errors.append("raw_inputs.spread_bps: out of range [0, 5000]")

    if not isinstance(term, int):
        errors.append("raw_inputs.term_months: must be an integer")
    elif term < 1 or term > 600:
        errors.append("raw_inputs.term_months: out of range [1, 600]")

    if not isinstance(start_date, str):
        errors.append("raw_inputs.start_date: must be a string (ISO 8601)")
    else:
        try:
            datetime.fromisoformat(start_date)
        except ValueError:
            errors.append("raw_inputs.start_date: not a valid ISO 8601 date")

    if not isinstance(rate_index, str) or not rate_index.strip():
        errors.append("raw_inputs.rate_index: must be a non-empty string")

    # Required fields from market-context
    gtap_code = ctx.get("gtap_commodity_code")
    corridor = ctx.get("corridor")
    tariff_pct = ctx.get("tariff_assumption_pct")
    rate_curve = ctx.get("rate_curve_index")

    if not isinstance(gtap_code, str) or not gtap_code.strip():
        errors.append("market_context.gtap_commodity_code: must be a non-empty string")
    if not isinstance(corridor, dict) or not corridor.get("origin") or not corridor.get("destination"):
        errors.append("market_context.corridor: must be {origin, destination} with both set")
    if tariff_pct is not None and (not _is_finite_number(tariff_pct) or tariff_pct < 0 or tariff_pct > 5):
        # 5.0 = 500% — anything beyond that suggests unit error (decimal vs percent)
        errors.append("market_context.tariff_assumption_pct: out of range [0, 5] (decimal)")
    if not isinstance(rate_curve, str) or not rate_curve.strip():
        errors.append("market_context.rate_curve_index: must be a non-empty string")

    if errors:
        return {
            "validation_errors": errors,
            "audit_log": [
                _audit_entry(
                    "validator",
                    f"✗ {len(errors)} validation error(s)",
                    {"errors": errors},
                )
            ],
        }

    # All clean. Construct the canonical validated_inputs object.
    # This is the ONLY producer of `validated_inputs` (invariant I2).
    validated = {
        "loan": {
            "notional_usd": float(notional),
            "spread_bps": float(spread),
            "term_months": int(term),
            "start_date": start_date,
            "rate_index": rate_index,
        },
        "market": {
            "gtap_commodity_code": gtap_code,
            "corridor": corridor,
            "tariff_assumption_pct": float(tariff_pct) if tariff_pct is not None else None,
            "rate_curve_index": rate_curve,
        },
    }
    return {
        "validated_inputs": validated,
        "validation_errors": [],
        "audit_log": [
            _audit_entry(
                "validator",
                "✓ all inputs valid",
                {"validated_keys": list(validated.keys())},
            )
        ],
    }


# ───────────────────────────────────────────────────────────────────────
# N4 — SIMULATION  (THE KNOT)
# ───────────────────────────────────────────────────────────────────────

def simulation_node(state: dict) -> dict:
    """N4 — deterministic. Calls DRAPS run_simulation.

    INVARIANT I1: this function does NOT read state['prompt'].
    It reads ONLY `validated_inputs`. Grep this file for 'prompt' — never appears.
    """
    validated = state.get("validated_inputs")
    if validated is None:
        # This should never happen: the graph routing guarantees we only enter here on pass.
        raise RuntimeError(
            "simulation_node called without validated_inputs. "
            "This indicates a bug in graph wiring — the boundary was bypassed."
        )

    # Iter-6a (D3): v2_direct compute+ACTUS path. When the composer ran
    # dispatch='v2_direct' (mode='derived') it derived the SOFR path + swap fixed
    # rates in V2 and stamped them onto knot_payload['v2_direct']. That path
    # bypasses DRAPS entirely and POSTs the A/B/C contract batches straight to the
    # ACTUS risk engine. Detected here as a NEW consumer of this node (purely
    # additive: it sits AFTER the validated-None wiring guard, which must stay
    # first, and BEFORE the supplied/draps_v1 logic, which stays byte-identical).
    # v2_direct is mode='derived' and never sets state['supplied'], so it cannot
    # collide with the supplied guard below.
    knot = state.get("knot_payload")
    if isinstance(knot, dict) and knot.get("v2_direct") is not None:
        spec = state.get("resolved_hedge_spec") or {}
        result = actus_client.run_v2_direct(knot, spec)
        summary = (
            f"A=${result.get('A_total', 0):,.0f} "
            f"B=${result.get('B_total', 0):,.0f} "
            f"C=${result.get('C_total', 0):,.0f} (v2_direct)"
        )
        return {
            "simulation_result": result,
            "audit_log": [
                _audit_entry(
                    "simulation",
                    summary,
                    {"dispatch": "v2_direct", "keys": list(result.keys())},
                )
            ],
        }

    # Iter-3 deliverable 4c (D3: honest deferral). When the caller supplied a SOFR
    # path + fixed rates via POST /run, the request lands in state['supplied'] and
    # the composer carries it onto knot_payload — but DRAPS itself derives the
    # SOFR path internally (inline Postman JS in DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json)
    # and has no code path to honor a supplied override. Rather than silently
    # ignore the caller-supplied numbers (which would produce a derived-mode
    # result mislabelled as supplied), raise NotImplementedError here naming the
    # bridge as the pending piece. The two viable follow-up paths are documented
    # in PROJECT_CONTEXT.md (after Iter-3 ships).
    if state.get("supplied") is not None:
        raise NotImplementedError(
            "simulation_node: state['supplied'] is present but the DRAPS bridge "
            "for caller-supplied SOFR paths is not yet implemented (Iter-3 "
            "deliverable 4c, D3 honest-deferral boundary). DRAPS derives SOFR "
            "internally via the inline Postman JS in "
            "DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json and there is no code path to "
            "override that with a supplied path.\n\n"
            "Two viable bridge paths for a follow-up iteration:\n"
            "  (a) modify DRAPS-side Postman JS to honor a supplied_sofr_path "
            "in configData\n"
            "  (b) skip DRAPS in supplied mode and call ACTUS directly from V2\n\n"
            "Refusing to silently fall back to derivation; the caller's "
            "authorisation of specific numbers is the entire contract of "
            "supplied mode."
        )

    # Real DRAPS call. May raise NotImplementedError until the contract is verified
    # (see draps_client.py and DESIGN/DESIGN1/design-1-detailed-design.md §6 note 1).
    result = draps_client.run_simulation(validated)

    summary = (
        f"A=${result.get('A_total', 0):,.0f} "
        f"B=${result.get('B_total', 0):,.0f} "
        f"C=${result.get('C_total', 0):,.0f}"
    )
    return {
        "simulation_result": result,
        "audit_log": [_audit_entry("simulation", summary, {"keys": list(result.keys())})],
    }


# ───────────────────────────────────────────────────────────────────────
# N6 — DISCLOSURE
# ───────────────────────────────────────────────────────────────────────

def disclosure_node(state: dict) -> dict:
    """N6 — deterministic. Calls ACTUS-Mentor /generate-xbrl-report (templating, not RAG).

    Two calls per design: one for the loan side, one for the hedge side.
    """
    sim = state.get("simulation_result") or {}
    validated = state.get("validated_inputs") or {}
    events = sim.get("events") or []

    # Real ACTUS-Mentor calls. May raise NotImplementedError until verified
    # (see actus_mentor_client.py and DESIGN/DESIGN1/design-1-detailed-design.md §6 note 2).
    doc = actus_mentor_client.generate_xbrl_report(
        events=events,
        contract_info={"loan": validated.get("loan", {}), "market": validated.get("market", {})},
        taxonomy="both",  # IFRS + US-GAAP per design
    )

    return {
        "disclosure_doc": doc,
        "audit_log": [
            _audit_entry(
                "disclosure",
                "IFRS + US-GAAP XBRL generated",
                {"taxonomies": doc.get("taxonomies", [])},
            )
        ],
    }


# ───────────────────────────────────────────────────────────────────────
# N8 — MEMORY
# ───────────────────────────────────────────────────────────────────────

def memory_node(state: dict) -> dict:
    """N8 — deterministic. Persist the recommendation for the predicted-vs-realised loop.

    This is the only genuinely new build per the design.
    """
    record_id = memory_store.save(
        thread_id=state["thread_id"],
        validated_inputs=state.get("validated_inputs") or {},
        simulation_result=state.get("simulation_result") or {},
        recommendation=state.get("recommendation") or {},
        audit_log=state.get("audit_log") or [],
    )
    return {
        "memory_record_id": record_id,
        "audit_log": [
            _audit_entry("memory", f"stored as {record_id}", {"record_id": record_id})
        ],
    }


# ───────────────────────────────────────────────────────────────────────
# NX — GIVE-UP  (honest failure, no fabrication)
# ───────────────────────────────────────────────────────────────────────

def give_up_node(state: dict) -> dict:
    """NX — deterministic. Honest termination after exhausted retries.

    INVARIANT I5: returns a structured failure. Never a fake result.
    """
    last_node = "validator"
    audit = state.get("audit_log") or []
    if audit:
        last_node = audit[-1].get("node", "validator")

    failure = {
        "reason": "validation_failed_max_retries",
        "errors": state.get("validation_errors") or [],
        "retry_count": state.get("retry_count", 0),
        "last_node": last_node,
    }
    return {
        "failure": failure,
        "audit_log": [
            _audit_entry(
                "give_up",
                f"giving up after {failure['retry_count']} retries",
                failure,
            )
        ],
    }
