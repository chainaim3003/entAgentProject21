"""
graph.py — LangGraph wiring for the ACTUS Hedge Advisor bow-tie.

V2 wiring (Iteration 1+):
  • HedgeAdvisorState now carries V2 config-architecture fields (business_identity,
    risk_factor_profile_id, resolved_risk_profile, hedge_spec_id, resolved_hedge_spec,
    knot_payload, profile_resolution_path) alongside the original V1 fields.
  • The validator's "pass" edge no longer goes straight to the knot.
    It now traverses N3a (profile_resolver) -> N3b (hedge_spec_resolver) ->
    N3c (profile_spec_validator) -> N3d (composer) -> N4 (simulation).
  • The composer is the boundary: it produces `knot_payload`. The Iteration-1
    composer (dispatch=draps_v1) is structurally pass-through with provenance
    stamps, so simulation_node continues to read validated_inputs and byte-
    equality with V1 is preserved.

Invariants enforced by code shape (not by comments):
  I1  prompt never appears as input to N4 (simulation).
  I2  validated_inputs has one producer (validator) and one consumer (simulation).
  I3  every node appends to audit_log via the operator.add reducer.
  I4  retry edge bounded by retry_count < MAX_VALIDATOR_RETRIES.
  I5  on failure, give_up_node terminates honestly. No fabricated result.
  I6  byte-equality test (tests/test_byte_equality_v1.py) stays green from
      Iteration 1 onward.

References:
  • DESIGN/DESIGN-V1/design-v1-detailed-design.md §1 (textual graph)
  • DESIGN/DESIGN-V1/design-v1-iteration-plan.md ("ITERATION 1 — Byte-Equality Replay")
  • DESIGN/DESIGN-V1/design-v1-config-architecture.md §4 (resolver + merge)
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from composer import composer_node
from config import settings
from deterministic_agents import (
    disclosure_node,
    give_up_node,
    memory_node,
    simulation_node,
    validator_node,
)
from hedge_spec_resolver import hedge_spec_resolver_node
from profile_resolver import profile_resolver_node
from profile_spec_validator import profile_spec_validator_node
from provenance import provenance_node
from reasoning_agents import (
    intake_node,
    interpretation_node,
    market_context_node,
    orchestrator_node,
)


# ───────────────────────────────────────────────────────────────────────
# State
# ───────────────────────────────────────────────────────────────────────

class HedgeAdvisorState(TypedDict, total=False):
    """The shared state. Every node reads what it needs, writes a partial delta.

    LangGraph merges the delta into this dict and checkpoints it after every node.
    """

    # Inputs (from user, via /run)
    prompt: str
    private_loan_doc: str
    thread_id: str

    # Produced by N1 INTAKE  [PRIVATE data enters here]
    raw_inputs: dict | None

    # Produced by N2 MARKET-CONTEXT  [PUBLIC data enters here]
    public_market_context: dict | None

    # Produced by N3 INPUT-VALIDATOR  (the V1 boundary)
    validated_inputs: dict | None
    validation_errors: list[str]
    retry_count: int

    # === V2 additions (Iteration 1+) ====================================
    # Produced by N3a PROFILE-RESOLVER
    business_identity: dict | None
    risk_factor_profile_id: str | None
    resolved_risk_profile: dict | None
    profile_resolution_path: list[str]

    # Produced by N3b HEDGE-SPEC-RESOLVER
    hedge_spec_id: str | None
    resolved_hedge_spec: dict | None

    # === Iteration-3 addition ===========================================
    # Populated by the request handler (POST /run) when the request body carries
    # a `supplied` block. Read by the composer (N3d) for mode='supplied' to
    # build a knot_payload that carries the caller's SOFR path + fixed rates
    # verbatim. Absent for derived-mode runs.
    # Shape: {sofr_path: [{time, value}, ...], swap_now_fixed: float, swap_later_fixed: float}
    supplied: dict | None
    # ====================================================================

    # Produced by N3d COMPOSER  (the V2 boundary; structurally pass-through in Iteration 1)
    knot_payload: dict | None
    # ====================================================================

    # Produced by N4 SIMULATION  (THE KNOT)
    simulation_result: dict | None  # {A_total, B_total, C_total, events}

    # Produced by N5 INTERPRETATION
    recommendation: dict | None  # {winner, $saving, cost_of_delay, why}

    # Produced by N6 DISCLOSURE
    disclosure_doc: dict | None  # IFRS / US-GAAP XBRL

    # Produced by N6a PROVENANCE  (Iter-3 minimal version; Iter-5 enforces I7)
    provenance_report: dict | None  # {stamps, mode, stamped_at, summary}

    # Produced by N8 MEMORY
    memory_record_id: str | None

    # Produced by NX GIVE-UP
    failure: dict | None  # {reason, errors, last_node}

    # Appended by every node — reducer concatenates (I3)
    audit_log: Annotated[list[dict[str, Any]], operator.add]


# ───────────────────────────────────────────────────────────────────────
# Conditional routing
# ───────────────────────────────────────────────────────────────────────

def route_after_validator(state: HedgeAdvisorState) -> Literal["pass", "retry", "fail"]:
    """Pure function of persisted state — replayable from any checkpoint.

    pass   -> validated_inputs is clean, into the V2 resolver chain
    retry  -> errors present, retry budget remains, back to N1 INTAKE
    fail   -> retries exhausted, NX GIVE-UP, honest termination
    """
    errors = state.get("validation_errors") or []
    if not errors:
        return "pass"
    if state.get("retry_count", 0) < settings.max_validator_retries:
        return "retry"
    return "fail"


def route_after_profile_spec_validator(state: HedgeAdvisorState) -> Literal["pass", "fail"]:
    """Pure function of persisted state — replayable from any checkpoint.

    Iteration-2 routing per design-v1-config-architecture.md §4 and §6.

    pass -> profile + spec are valid; into composer (N3d) -> simulation (N4)
    fail -> validation_errors present (from N3a resolver OR N3c validator);
            into NX GIVE-UP. There is no retry path here — the profile/spec
            are config artifacts, not LLM extraction, so retrying intake
            won't help. The user must fix config and re-run.
    """
    errors = state.get("validation_errors") or []
    return "fail" if errors else "pass"


# ───────────────────────────────────────────────────────────────────────
# Graph construction
# ───────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Wire the V2 bow-tie: 8 agents + 5 new resolver/composer/provenance nodes + give-up.

    Returns an uncompiled StateGraph. Caller compiles with a checkpointer.

    Iteration 2 wires the second conditional edge: after N3c, validation_errors
    (from N3a resolver OR N3c validator) route to give_up; otherwise to composer.
    The retry path stays attached to the V1 boundary only (N3 -> N1) because the
    V2 chain operates on config artifacts, not LLM extraction — retrying intake
    can't fix a missing profile or a malformed component spec.
    """
    g: StateGraph = StateGraph(HedgeAdvisorState)

    # ── Register V1 nodes ──
    g.add_node("orchestrator", orchestrator_node)        # N0  reasoning
    g.add_node("intake", intake_node)                    # N1  reasoning
    g.add_node("market_context", market_context_node)    # N2  reasoning
    g.add_node("validator", validator_node)              # N3  deterministic — V1 boundary
    g.add_node("simulation", simulation_node)            # N4  deterministic — KNOT
    g.add_node("interpretation", interpretation_node)    # N5  reasoning
    g.add_node("disclosure", disclosure_node)            # N6  deterministic
    g.add_node("provenance", provenance_node)            # N6a deterministic (NEW Iter-3)
    g.add_node("memory", memory_node)                    # N8  deterministic
    g.add_node("give_up", give_up_node)                  # NX  deterministic

    # ── Register V2 nodes (Iteration 1) ──
    g.add_node("profile_resolver", profile_resolver_node)              # N3a
    g.add_node("hedge_spec_resolver", hedge_spec_resolver_node)        # N3b
    g.add_node("profile_spec_validator", profile_spec_validator_node)  # N3c
    g.add_node("composer", composer_node)                              # N3d — V2 boundary

    # ── Linear edges: left wing → V1 validator ──
    g.add_edge(START, "orchestrator")
    g.add_edge("orchestrator", "intake")
    g.add_edge("intake", "market_context")
    g.add_edge("market_context", "validator")

    # ── Conditional edge at the V1 boundary ──
    # On "pass", instead of going straight to simulation, we go through the V2 chain.
    g.add_conditional_edges(
        "validator",
        route_after_validator,
        {
            "pass": "profile_resolver",   # → V2 chain → composer → simulation
            "retry": "intake",            # bounded retry, back to extraction
            "fail": "give_up",            # honest termination
        },
    )

    # ── V2 chain: profile_resolver → hedge_spec_resolver → profile_spec_validator → composer → simulation ──
    g.add_edge("profile_resolver", "hedge_spec_resolver")
    g.add_edge("hedge_spec_resolver", "profile_spec_validator")

    # ── Conditional edge at the V2 boundary (Iteration 2) ──
    # N3c is the final gate before the knot. On pass, into composer + simulation.
    # On fail, honest termination via give_up. No retry: config errors need a
    # human edit, not another LLM pass.
    g.add_conditional_edges(
        "profile_spec_validator",
        route_after_profile_spec_validator,
        {
            "pass": "composer",
            "fail": "give_up",
        },
    )
    g.add_edge("composer", "simulation")

    # ── Right wing (linear): knot → interpretation → disclosure → memory → END ──
    g.add_edge("simulation", "interpretation")
    g.add_edge("interpretation", "disclosure")
    g.add_edge("disclosure", "provenance")
    g.add_edge("provenance", "memory")
    g.add_edge("memory", END)

    # ── Failure path → END ──
    g.add_edge("give_up", END)

    return g


def compile_app(checkpointer: SqliteSaver):
    """Compile the graph with a checkpointer attached.

    Separated so tests can compile with MemorySaver and prod uses SqliteSaver.
    """
    return build_graph().compile(checkpointer=checkpointer)
