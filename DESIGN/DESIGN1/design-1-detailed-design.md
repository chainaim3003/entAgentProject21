# Project 2 — ACTUS Hedge Advisor
## design-1: Detailed Design (Textual Graph + Verification + Bottom Line)

> **Source:** `C:\SATHYA\CHAINAIM3003\mcp-servers\LEGENT-PROC\PROJECT2_BOWTIE_REFRAMED.md` (Sections 5, 6, Bottom line)
> plus the textual graph response from chat "Long FIN Agents-Team-1" (https://claude.ai/chat/a0d16ca6-e71f-4eb7-84b5-5eee99c81124),
> produced in response to "Can u also show a textual graph of the multiple agents?"
> **Date extracted:** 2026-05-15

---

## 1. Textual graph — nodes, edges, what flows between them

This is the detailed graph representation that complements the bow-tie diagram in `design-1-conceptual-design.md`. Each agent is given a node ID; edges are explicit; the two structural invariants (prompt boundary, clean-inputs gate) are stated explicitly.

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

## 5. Why this framing is the right one

It is neither academic nor a sales deck, because the bow-tie is an **engineering law with a dollar consequence** — and it is the same law the enterprise-AI field is converging on in 2026 under "deterministic guardrails." The three properties enterprises screen for — efficiency, interoperability, auditability — are not features added to this design; they are what the stochastic/deterministic separation *produces*, expressed as a multi-agent wiring diagram. Project 2 is the application of that law to agentic AI, demonstrated on a real supply-chain loan, with an open interoperability standard (ACTUS) as the load-bearing wall.

---

## 6. What still must be verified before commit

- **DRAPS `run_simulation` interface.** Verified: the DRAPS demo file is a Postman collection with a deterministic JavaScript derivation engine that builds PAM+SWAPS contracts from structured inputs and POSTs to ACTUS `:8083` — it is reusable deterministic code, not a Claude-Desktop-only flow, and the loan is already USD-denominated. Still to confirm: the exact input/output contract of the `generalRisk` MCP server's `run_simulation` tool (`SWAPS-interface/Backend/src/mcp-server.ts` in the GitHub repo — not on the local path, which holds the ACTUS risk service). This defines exactly what the Input-Validator Agent must produce.

- **ACTUS-Mentor XBRL endpoint.** Note 2: the design assumes `/generate-xbrl-report` is a deterministic templating path, not the RAG graph — which is why the Disclosure Agent is classified deterministic. This needs confirming by reading ACTUS-Mentor's `api_server.py` (on local disk). If that endpoint actually invokes the 7-agent graph, the classification — and the bow-tie discipline applied to it — must be revisited.

- **ACTUS-Mentor backend liveness.** The frontend at 52.73.253.140 is confirmed serving; the FastAPI backend on :8000 needs a direct liveness check.

- **Brammertz/Kubli Figures 1 and 2.** The bow-tie structure here is reconstructed from the paper's detailed prose description of each figure. The figure images were not extracted from the PDF — confirm against originals if used verbatim. The paper describes the converge-knot-fan structure but does not use the word "bow-tie"; the term is corroborated by a separate ACTUS source (researchfeatures.com).

- **Adoption and market figures.** The "88% of pilots never reach production" figure and the SCF market sizes are third-party estimates gathered via web search; sources vary; ranges shown. Pull primary reports before formal external use. The "spreadsheets and a treasurer's intuition" characterization of current practice is a fair general claim, not a cited statistic.

---

## Bottom line

Project 2 reframed: the problem is an engineering failure — the probabilistic engine in the wrong place, with no discipline about which agents in a multi-agent system are allowed to be probabilistic. The solution is that discipline made into a wiring diagram — reasoning agents on the stochastic wings, deterministic agents at the knot, a validator as the boundary, a memory loop closing it, an orchestrator driven by prompts that never reach the core. Every enterprise wall — demo-to-prod, public/private fusion, long-running tasks, evals, auditability, efficiency, memory — is cleared by the structure, not by a feature bolted on after. The components are largely built: DRAPS is the verified deterministic core, the ACTUS engine runs locally, ACTUS-Mentor is the verified right-wing reporting asset. The new code is small — three wing reasoning agents, a validator, a memory store, a thin orchestrator — and there are no mocks, no hardcoding, no fallbacks, because every deterministic piece already runs. Two interface reads remain before build; neither is an architecture risk.

---

**End of design-1-detailed-design.md**
