"""
reasoning_agents.py — N0, N1, N2, N5  (all use Gemini).

This file imports the Gemini client. That import is the agent-type law made visible:
deterministic_agents.py has zero Gemini imports.

Per design:
  N0 Orchestrator     — decomposes the prompt, sequences agents (no domain work itself)
  N1 Intake           — private loan doc -> raw structured inputs
  N2 Market-Context   — public data resolution (GTAP code, corridor, tariff sanity-check)
  N5 Interpretation   — A/B/C simulation result -> recommendation + the "why"

References:
  • DESIGN/DESIGN1/design-1-detailed-design.md §1 (textual graph nodes)
  • DESIGN/DESIGN1/design-1-problem-solution-impact.md §2 (agent roles)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from gemini_client import extract_structured, generate_text


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


# ───────────────────────────────────────────────────────────────────────
# N0 — ORCHESTRATOR
# ───────────────────────────────────────────────────────────────────────

ORCHESTRATOR_SYSTEM = """\
You are the orchestrator of a multi-agent hedge-advisor system.
Your job: decompose the user's hedging question into a plan.
You do NOT do any domain work. You produce a structured plan only.

The plan describes which downstream agents are needed, in what order, and what each must produce.
Output JSON only.
"""

ORCHESTRATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "plan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step": {"type": "integer"},
                    "agent": {"type": "string"},
                    "produces": {"type": "string"},
                },
                "required": ["step", "agent", "produces"],
            },
        },
        "user_goal": {"type": "string"},
    },
    "required": ["plan", "user_goal"],
}


def orchestrator_node(state: dict) -> dict:
    """N0 — reasoning (Gemini). Decompose the user ask into a plan."""
    user_msg = (
        f"User prompt: {state['prompt']}\n\n"
        f"Private loan document available: {'yes' if state.get('private_loan_doc') else 'no'}"
    )
    plan = extract_structured(
        prompt=user_msg,
        response_schema=ORCHESTRATOR_SCHEMA,
        system_instruction=ORCHESTRATOR_SYSTEM,
    )
    return {
        "retry_count": 0,
        "audit_log": [
            _audit_entry(
                "orchestrator",
                f"Planned {len(plan['plan'])} steps; goal: {plan['user_goal'][:80]}",
                plan,
            )
        ],
    }


# ───────────────────────────────────────────────────────────────────────
# N1 — INTAKE  (private data enters here)
# ───────────────────────────────────────────────────────────────────────

INTAKE_SYSTEM = """\
You extract a structured loan record from a private loan document and the user's question.
Output JSON only, conforming to the schema. If a field cannot be determined from the document,
return null for that field — do NOT invent values.

Fields:
  notional_usd     — loan principal in USD (number)
  spread_bps       — credit spread over the reference rate, in basis points (number)
  term_months      — original tenor in months (integer)
  start_date       — origination date, ISO 8601 (YYYY-MM-DD)
  rate_index       — reference rate name (e.g. SOFR, LIBOR, EURIBOR)
  commodity_hint   — what the loan is financing, free text (e.g. "textiles imported from India")
  corridor_hint    — origin->destination if mentioned (e.g. "India to US")
"""

INTAKE_SCHEMA = {
    "type": "object",
    "properties": {
        "notional_usd": {"type": ["number", "null"]},
        "spread_bps": {"type": ["number", "null"]},
        "term_months": {"type": ["integer", "null"]},
        "start_date": {"type": ["string", "null"]},
        "rate_index": {"type": ["string", "null"]},
        "commodity_hint": {"type": ["string", "null"]},
        "corridor_hint": {"type": ["string", "null"]},
    },
    "required": [
        "notional_usd",
        "spread_bps",
        "term_months",
        "start_date",
        "rate_index",
        "commodity_hint",
        "corridor_hint",
    ],
}


def intake_node(state: dict) -> dict:
    """N1 — reasoning (Gemini). Extract structured loan record. PRIVATE data enters here."""
    retry_hint = ""
    if state.get("validation_errors"):
        retry_hint = (
            "\n\nPRIOR EXTRACTION FAILED VALIDATION. Errors:\n"
            + "\n".join(f" - {e}" for e in state["validation_errors"])
            + "\nCorrect the fields and try again."
        )

    msg = (
        f"User question: {state['prompt']}\n\n"
        f"Private loan document:\n{state.get('private_loan_doc', '')}"
        f"{retry_hint}"
    )

    raw = extract_structured(
        prompt=msg,
        response_schema=INTAKE_SCHEMA,
        system_instruction=INTAKE_SYSTEM,
    )

    summary_bits = []
    if raw.get("notional_usd") is not None:
        summary_bits.append(f"notional=${raw['notional_usd']:,.0f}")
    if raw.get("term_months") is not None:
        summary_bits.append(f"term={raw['term_months']}mo")
    if raw.get("commodity_hint"):
        summary_bits.append(raw["commodity_hint"])
    summary = "extracted " + ", ".join(summary_bits) if summary_bits else "extracted (with nulls)"

    return {
        "raw_inputs": raw,
        "retry_count": state.get("retry_count", 0) + (1 if state.get("validation_errors") else 0),
        "validation_errors": [],  # clear on each new intake pass
        "audit_log": [_audit_entry("intake", summary, raw)],
    }


# ───────────────────────────────────────────────────────────────────────
# N2 — MARKET-CONTEXT  (public data enters here)
# ───────────────────────────────────────────────────────────────────────

MARKET_CONTEXT_SYSTEM = """\
You resolve public market context for a trade-finance loan, given the raw extraction from a private loan document.

Output JSON only:
  gtap_commodity_code   — GTAP commodity code best matching the commodity_hint (string, e.g. "50" for textiles)
  corridor              — origin and destination country ISO codes (e.g. {"origin": "IN", "destination": "US"})
  tariff_assumption_pct — current tariff rate as a decimal (e.g. 0.25 for 25%); null if unknown
  rate_curve_index      — the appropriate forward curve identifier (e.g. "USD-SOFR-FORWARD")
  notes                 — short free-text rationale

Do NOT invent values. Use null when you cannot ground the field in public knowledge.
"""

MARKET_CONTEXT_SCHEMA = {
    "type": "object",
    "properties": {
        "gtap_commodity_code": {"type": ["string", "null"]},
        "corridor": {
            "type": ["object", "null"],
            "properties": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
            },
        },
        "tariff_assumption_pct": {"type": ["number", "null"]},
        "rate_curve_index": {"type": ["string", "null"]},
        "notes": {"type": "string"},
    },
    "required": [
        "gtap_commodity_code",
        "corridor",
        "tariff_assumption_pct",
        "rate_curve_index",
        "notes",
    ],
}


def market_context_node(state: dict) -> dict:
    """N2 — reasoning (Gemini). Resolve public market context. PUBLIC data enters here."""
    raw = state.get("raw_inputs") or {}
    msg = (
        "Raw extraction from the private loan:\n"
        f"  commodity_hint: {raw.get('commodity_hint')}\n"
        f"  corridor_hint:  {raw.get('corridor_hint')}\n"
        f"  rate_index:     {raw.get('rate_index')}\n"
        f"  start_date:     {raw.get('start_date')}\n"
        f"  term_months:    {raw.get('term_months')}\n"
        "\nResolve the public-data fields per schema."
    )

    ctx = extract_structured(
        prompt=msg,
        response_schema=MARKET_CONTEXT_SCHEMA,
        system_instruction=MARKET_CONTEXT_SYSTEM,
    )

    summary_bits = []
    if ctx.get("gtap_commodity_code"):
        summary_bits.append(f"GTAP={ctx['gtap_commodity_code']}")
    if ctx.get("corridor"):
        c = ctx["corridor"]
        summary_bits.append(f"{c.get('origin')}->{c.get('destination')}")
    if ctx.get("tariff_assumption_pct") is not None:
        summary_bits.append(f"tariff={ctx['tariff_assumption_pct']*100:.1f}%")
    summary = "resolved " + ", ".join(summary_bits) if summary_bits else "resolved (with nulls)"

    return {
        "market_context": ctx,
        "audit_log": [_audit_entry("market_context", summary, ctx)],
    }


# ───────────────────────────────────────────────────────────────────────
# N5 — INTERPRETATION  (right wing — explains the deterministic result)
# ───────────────────────────────────────────────────────────────────────

INTERPRETATION_SYSTEM = """\
You interpret the result of a deterministic ACTUS contract simulation that ran three hedge scenarios:
  A — no hedge (baseline)
  B — hedge now
  C — hedge in 3 months

You produce a recommendation with the winning scenario and the dollar 'why'.

Output JSON only:
  winner               — "A" | "B" | "C"
  predicted_saving_usd — saving of winner vs A (no-hedge baseline), in USD
  cost_of_delay_usd    — saving of B over C (cost of waiting 3mo to hedge), in USD; null if not applicable
  rationale            — short, plain-English explanation (3–6 sentences, no jargon)

Do NOT add scenarios, do NOT invent numbers — use only what the simulation_result provides.
"""

INTERPRETATION_SCHEMA = {
    "type": "object",
    "properties": {
        "winner": {"type": "string", "enum": ["A", "B", "C"]},
        "predicted_saving_usd": {"type": "number"},
        "cost_of_delay_usd": {"type": ["number", "null"]},
        "rationale": {"type": "string"},
    },
    "required": ["winner", "predicted_saving_usd", "cost_of_delay_usd", "rationale"],
}


def interpretation_node(state: dict) -> dict:
    """N5 — reasoning (Gemini). Turn deterministic A/B/C totals into a recommendation + 'why'."""
    sim = state.get("simulation_result") or {}
    msg = (
        "Simulation result (deterministic, from DRAPS run_simulation):\n"
        f"  A_total (no hedge):      {sim.get('A_total')}\n"
        f"  B_total (hedge now):     {sim.get('B_total')}\n"
        f"  C_total (hedge in 3mo):  {sim.get('C_total')}\n"
        "\nPick the winner, compute predicted saving vs A, cost of delay (B vs C), "
        "and explain why."
    )
    rec = extract_structured(
        prompt=msg,
        response_schema=INTERPRETATION_SCHEMA,
        system_instruction=INTERPRETATION_SYSTEM,
    )
    summary = (
        f"winner={rec['winner']}, "
        f"saving=${rec['predicted_saving_usd']:,.0f}"
    )
    return {
        "recommendation": rec,
        "audit_log": [_audit_entry("interpretation", summary, rec)],
    }
