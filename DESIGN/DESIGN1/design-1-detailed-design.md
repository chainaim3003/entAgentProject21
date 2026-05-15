# Project 2 — ACTUS Hedge Advisor
## design-1: Detailed Design (Textual Graph of Agents + Edges + Invariants)

> **Source:** Extracted from chat "Long FIN Agents-Team-1"
> (https://claude.ai/chat/a0d16ca6-e71f-4eb7-84b5-5eee99c81124)
> **Date extracted:** 2026-05-15

---

## 1. Textual graph — nodes, edges, what flows between them

```
================================================================================
  PROJECT 2  -  TEXTUAL GRAPH  ::  Agents and Edges
================================================================================

NODES (the agents)
==================

  N0  ORCHESTRATOR
        type        : reasoning  (Gemini Pro)
        zone        : control plane
        consumes    : prompt, private_loan_doc
        produces    : plan, retry_count, audit_log

  N1  INTAKE
        type        : reasoning  (Gemini)
        zone        : left wing
        consumes    : prompt, private_loan_doc, validation_errors (on retry)
        produces    : raw_inputs                       [PRIVATE data enters here]

  N2  MARKET-CONTEXT
        type        : reasoning  (Gemini)
        zone        : left wing
        consumes    : raw_inputs
        produces    : market_context                   [PUBLIC data enters here]

  N3  INPUT-VALIDATOR
        type        : DETERMINISTIC  (plain code, no LLM)
        zone        : boundary
        consumes    : raw_inputs, market_context
        produces    : validated_inputs  OR  validation_errors

  N4  SIMULATION
        type        : DETERMINISTIC  (DRAPS run_simulation MCP tool)
        zone        : KNOT
        consumes    : validated_inputs  (and ONLY this - never the prompt)
        produces    : simulation_result   { A_total, B_total, C_total, events }

  N5  INTERPRETATION
        type        : reasoning  (Gemini)
        zone        : right wing
        consumes    : simulation_result
        produces    : recommendation       { winner, $saving, cost_of_delay, why }

  N6  DISCLOSURE
        type        : DETERMINISTIC  (ACTUS-Mentor /generate-xbrl-report)
        zone        : right wing
        consumes    : simulation_result.events, validated_inputs
        produces    : disclosure_doc       (IFRS / US-GAAP XBRL)

  N7  EXPLANATION   [OPTIONAL - off critical path]
        type        : reasoning  (ACTUS-Mentor RAG pipeline)
        zone        : right wing  (side assistant)
        consumes    : user follow-up question (out-of-band)
        produces    : explanation

  N8  MEMORY
        type        : DETERMINISTIC  (persistence)
        zone        : feedback loop
        consumes    : validated_inputs, simulation_result, recommendation, audit_log
        produces    : memory_record_id

  NX  GIVE-UP
        type        : DETERMINISTIC  (clean termination)
        zone        : failure path
        consumes    : audit_log, validation_errors
        produces    : honest failure  (NOT a fabricated result)

  END
        terminal node


EDGES (the flow)
================

  edge        from           to                 carries
  ----------------------------------------------------------------------------
  e0  START              -> N0  ORCHESTRATOR     prompt, private_loan_doc
  e1  N0  ORCHESTRATOR   -> N1  INTAKE           prompt, private_loan_doc
  e2  N1  INTAKE         -> N2  MARKET-CONTEXT   raw_inputs
  e3  N2  MARKET-CONTEXT -> N3  INPUT-VALIDATOR  raw_inputs + market_context
  e4  N3  INPUT-VALIDATOR -> N4 SIMULATION       validated_inputs    [if PASS]
  e5  N3  INPUT-VALIDATOR -> N1 INTAKE           validation_errors   [if FAIL
                                                  AND retry_count<MAX]
  e6  N3  INPUT-VALIDATOR -> NX GIVE-UP          validation_errors   [if FAIL
                                                  AND retry_count>=MAX]
  e7  N4  SIMULATION     -> N5  INTERPRETATION   simulation_result
  e8  N5  INTERPRETATION -> N6  DISCLOSURE       simulation_result + recommendation
  e9  N6  DISCLOSURE     -> N8  MEMORY           full state so far
  e10 N7  EXPLANATION    -> (out-of-band)        side query, not in critical flow
  e11 N8  MEMORY         -> END
  e12 NX  GIVE-UP        -> END


THE TWO STRUCTURAL LINES
========================

  PROMPT BOUNDARY
    only N0 (ORCHESTRATOR) and the wings (N1, N2) ever see `prompt`.
    N4 SIMULATION reads `validated_inputs` only.
    Searching the graph for nodes that read `prompt` is a one-line audit.

  CLEAN-INPUTS GATE
    only N3 INPUT-VALIDATOR can produce `validated_inputs`.
    only N4 SIMULATION reads `validated_inputs`.
    No other edge carries it. The boundary is enforced by data flow.


CONDITIONAL ROUTING  (the only non-linear edge)
===============================================

  at  N3  INPUT-VALIDATOR :
      validation_errors == []                  -> e4  -> N4  (pass)
      validation_errors != [] AND retries < N  -> e5  -> N1  (bounded retry)
      validation_errors != [] AND retries >= N -> e6  -> NX  (give up cleanly)

  everywhere else: single deterministic outgoing edge.


ZONES  (the bow-tie, expressed as a node-partition)
===================================================

  control plane     = { N0 }
  left wing         = { N1, N2 }     (reasoning)
  boundary          = { N3 }          (deterministic gate)
  KNOT              = { N4 }          (deterministic core)
  right wing        = { N5, N6, N7 }  (mix)
  feedback loop     = { N8 }          (deterministic)
  failure path      = { NX }          (deterministic)


ZONE-COUNT BY AGENT TYPE
========================

  reasoning (Gemini, LLM):  N0, N1, N2, N5, N7        -> 5 nodes
  deterministic (no LLM) :  N3, N4, N6, N8, NX        -> 5 nodes

  enterprise cost story  :  half the graph is free deterministic compute.
                            Gemini runs only where input is genuinely ambiguous.


THE INVARIANTS  (properties enforced by the graph shape)
========================================================

  I1  prompt never appears as input to N4 (the knot).
        -> auditability: knot output reproducible from validated_inputs alone.

  I2  validated_inputs has exactly one producer (N3) and one consumer (N4).
        -> nothing schema-dirty can reach the deterministic core.

  I3  every node appends to audit_log.
        -> decision provenance: full chain available at END.

  I4  retry edge (e5) is bounded by retry_count.
        -> no infinite wing<->validator loop.

  I5  on failure, NX terminates honestly. No fallback that fabricates a result.
        -> demo-to-prod: failure modes are explicit, not papered over.
================================================================================
```

---

## 2. Mapping enterprise walls → graph constructs

| Enterprise wall | Graph construct that clears it |
|---|---|
| **Public + private data fusion** | N1 (private entry) and N2 (public entry) are on the same wing; N3 reconciles before crossing into the knot |
| **Long-running tasks** | Every node is a LangGraph checkpoint; `SqliteSaver`; `thread_id` resume |
| **Reasoning interweave** | N0 + N1 + N2 + N5 all reason; N3 + N4 + N6 + N8 commit deterministically |
| **Long-term memory** | N8's predicted-vs-realised loop; recalibration each quarter |

---

## 3. Verified external contracts (from files read in source chat)

### 3.1 DRAPS `run_simulation` MCP tool — N4 SIMULATION

**Status:** *contract still needs `mcp-server.ts` read.* The local `ACTUS-LOCAL-EXT` path holds the ACTUS engine, not the DRAPS MCP wrapper. The file is in the GitHub repo's `SWAPS-interface/Backend/`.

What is verified (from `SWAPS-1LOAN-WHAT-IF-DEMO.json`):
- DRAPS uses a deterministic JavaScript derivation engine (Postman pre-request script) to build PAM + SWAPS contracts from structured inputs
- It POSTs to ACTUS `:8083/eventsBatch`
- It is reusable deterministic code, not a Claude-Desktop-only flow
- The loan is already USD-denominated

What is NOT yet verified (the connector detail):
- Exact tool name, args, and return shape of `run_simulation` MCP tool

### 3.2 ACTUS-Mentor `/generate-xbrl-report` — N6 DISCLOSURE

**Status:** *verified as deterministic templating* (from `xbrl_output_generator.py`).

```python
# Request shape (XBRLReportRequest):
#   { actus_events: list, contract_info: dict, taxonomy: "ifrs"|"usgaap"|"both" }
# `actus_events` comes from state['simulation_result'] - specifically the events
# array DRAPS returns from the ACTUS server.
```

**Two design notes:**

1. The MVP does not override IP-event hedge-accounting tags. For the demo, the IP events are tagged as interest events — accurate as cash-flow descriptions, just not optimal hedge-accounting tags. Phase-2 work or a small extension of the mapping table.

2. The `hedge_relationship` block is new — neither `generate_xbrl_report` nor anything else on disk produces it today. It's a small deterministic function inside the Disclosure Agent, ~30 lines.

3. The Disclosure Agent calls `/generate-xbrl-report` **twice** — once for the loan side, once for the hedge side.

---

## 4. Detailed knot (N4) substructure

The simulation knot is actually three deterministic sub-steps (no agents, no LLM, all pure code/MCP):

```
                  [KNOT, all det, NO LLM]

   Derivation                       <- port of Postman prerequest JS
       (turn validated_inputs into ACTUS PAM+SWAPS payload)
                |
                v
   Scenario-Constructor             <- builds A/B/C payloads
       (Scenario A: no hedge)
       (Scenario B: hedge now)
       (Scenario C: hedge in 3 months)
                |
                v
   Simulation x3                    <- DRAPS run_simulation, A then B then C
       (call MCP tool with each payload, get events back)
                |
                v
   simulation_result = { A_total, B_total, C_total, events }
```

The right-wing A/B/C-Comparator (deterministic arithmetic, sits at the entry of N5) picks the winner — that's how the $41,875 / $17,025 numbers come out. The "why" is then written by N5 INTERPRETATION (Gemini).

---

## 5. The reuse story (what we build vs. what we reuse)

| Component | What it is | Build vs reuse |
|---|---|---|
| N0 Orchestrator | Gemini Pro on a LangGraph orchestrator | **NEW** (small) — wires the existing pieces |
| N1 Intake | Reasoning extraction from private loan doc | **NEW** (small) — Gemini call with schema |
| N2 Market-Context | Public data fetch (tariffs, Fed curve, etc.) | **NEW** (small) — Gemini + tool calls |
| N3 Input-Validator | Schema/type/range validation | **NEW** (small) — plain code |
| N4 Simulation | PAM + SWAPS simulation via ACTUS | **REUSE** — DRAPS already does this |
| N5 Interpretation | "Why" explanation of the winner | **NEW** (small) — Gemini with simulation result |
| N6 Disclosure | XBRL IFRS + US-GAAP | **REUSE** — ACTUS-Mentor `/generate-xbrl-report` |
| N7 Explanation | RAG side assistant | **REUSE** — ACTUS-Mentor RAG pipeline |
| N8 Memory | Predicted-vs-realised persistence loop | **NEW** — only genuinely new build |
| NX Give-Up | Clean failure termination | **NEW** (trivial) — plain code |

**Bottom line:** the deterministic *engines* are reused (DRAPS, ACTUS-Mentor). What's new is the **orchestration + memory** — which is the agentic-AI layer the hackathon asks for.

---

## 6. Honest gaps (marked `TODO: confirm contract` in the skeleton code)

I did **not** invent API shapes. Three places remain explicit TODOs in the skeleton on disk (`C:\SATHYA\CHAINAIM3003\mcp-servers\LEGENT-PROC\hedge_advisor_graph_skeleton.py`):

- **`simulation_node`** — exact `run_simulation` tool name, args, and return shape need the DRAPS `mcp-server.ts` read
- **`intake_node`** — its Gemini extraction schema must match DRAPS's input contract, so it's blocked on the same read
- **`disclosure_node`** — second-call payload for the hedge side needs the `hedge_relationship` block specified (~30 lines)

These are connector details, not architecture risks. The schematic stands regardless.

---

**End of design-1-detailed-design.md**
