"""
graph.py — LangGraph wiring for the ACTUS Hedge Advisor bow-tie.

Implements:
  • HedgeAdvisorState — the shared, checkpointed state object (one dict, every node reads/writes)
  • build_graph()    — wires N0..N8 + NX into the bow-tie shape, with the one conditional edge
  • route_after_validator — the only non-linear routing decision; pure function of state

Invariants enforced by code shape (not by comments):
  I1  prompt never appears as input to N4 (simulation): SIMULATION_NODE reads only `validated_inputs`.
  I2  validated_inputs has exactly one producer (validator) and one consumer (simulation).
  I3  every node appends to audit_log via the operator.add reducer.
  I4  retry edge bounded by retry_count < MAX_VALIDATOR_RETRIES.
  I5  on failure, give_up_node terminates honestly. No fabricated result.

References:
  • DESIGN/DESIGN1/design-1-detailed-design.md §1 (textual graph)
  • DESIGN/DESIGN1/design-1-project-structure.md §8 (state schema)
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from config import settings
from deterministic_agents import (
    disclosure_node,
    give_up_node,
    memory_node,
    simulation_node,
    validator_node,
)
from reasoning_agents import (
    intake_node,
    interpretation_node,
    market_context_node,
    orchestrator_node,
)


# ───────────────────────────────────────────────────────────────────────
# State (§8 of project-structure)
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
    market_context: dict | None

    # Produced by N3 INPUT-VALIDATOR  (the boundary)
    validated_inputs: dict | None
    validation_errors: list[str]
    retry_count: int

    # Produced by N4 SIMULATION  (THE KNOT — reads only validated_inputs)
    simulation_result: dict | None  # {A_total, B_total, C_total, events}

    # Produced by N5 INTERPRETATION
    recommendation: dict | None  # {winner, $saving, cost_of_delay, why}

    # Produced by N6 DISCLOSURE
    disclosure_doc: dict | None  # IFRS / US-GAAP XBRL

    # Produced by N8 MEMORY
    memory_record_id: str | None

    # Produced by NX GIVE-UP
    failure: dict | None  # {reason, errors, last_node}

    # Appended by every node — reducer concatenates (I3)
    audit_log: Annotated[list[dict[str, Any]], operator.add]


# ───────────────────────────────────────────────────────────────────────
# Conditional routing (the only non-linear edge in the graph)
# ───────────────────────────────────────────────────────────────────────

def route_after_validator(state: HedgeAdvisorState) -> Literal["pass", "retry", "fail"]:
    """Pure function of persisted state — replayable from any checkpoint.

    pass   -> validated_inputs is clean, into the knot (N4 SIMULATION)
    retry  -> errors present, retry budget remains, back to N1 INTAKE
    fail   -> retries exhausted, NX GIVE-UP, honest termination
    """
    errors = state.get("validation_errors") or []
    if not errors:
        return "pass"
    if state.get("retry_count", 0) < settings.max_validator_retries:
        return "retry"
    return "fail"


# ───────────────────────────────────────────────────────────────────────
# Graph construction
# ───────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Wire the 8 agents + give-up into the bow-tie.

    Returns an uncompiled StateGraph. Caller compiles with a checkpointer
    (see main.py for the SqliteSaver attach).
    """
    g: StateGraph = StateGraph(HedgeAdvisorState)

    # Register nodes
    g.add_node("orchestrator", orchestrator_node)        # N0  reasoning
    g.add_node("intake", intake_node)                    # N1  reasoning
    g.add_node("market_context", market_context_node)    # N2  reasoning
    g.add_node("validator", validator_node)              # N3  deterministic — boundary
    g.add_node("simulation", simulation_node)            # N4  deterministic — KNOT
    g.add_node("interpretation", interpretation_node)    # N5  reasoning
    g.add_node("disclosure", disclosure_node)            # N6  deterministic
    g.add_node("memory", memory_node)                    # N8  deterministic
    g.add_node("give_up", give_up_node)                  # NX  deterministic

    # Linear edges (the spine of the bow-tie)
    g.add_edge(START, "orchestrator")
    g.add_edge("orchestrator", "intake")
    g.add_edge("intake", "market_context")
    g.add_edge("market_context", "validator")

    # Conditional edges (the only branching point — at the boundary)
    g.add_conditional_edges(
        "validator",
        route_after_validator,
        {
            "pass": "simulation",   # clean inputs -> into the knot
            "retry": "intake",      # bounded retry, back to extraction
            "fail": "give_up",      # honest termination
        },
    )

    # Right wing (linear) — knot -> interpretation -> disclosure -> memory -> END
    g.add_edge("simulation", "interpretation")
    g.add_edge("interpretation", "disclosure")
    g.add_edge("disclosure", "memory")
    g.add_edge("memory", END)

    # Failure path -> END
    g.add_edge("give_up", END)

    return g


def compile_app(checkpointer: SqliteSaver):
    """Compile the graph with a checkpointer attached.

    Separated so tests can compile with MemorySaver and prod uses SqliteSaver.
    """
    return build_graph().compile(checkpointer=checkpointer)
