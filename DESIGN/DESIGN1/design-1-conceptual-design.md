# Project 2 — ACTUS Hedge Advisor
## design-1: Conceptual Design + Textual Visual Diagram

> **Source:** Extracted from chat "Long FIN Agents-Team-1"
> (https://claude.ai/chat/a0d16ca6-e71f-4eb7-84b5-5eee99c81124)
> **Date extracted:** 2026-05-15

---

## The shape: bow-tie multi-agent orchestration

The structure: **Prompt → Orchestrator** (Gemini, prompt stops here) → **Left Wing** (Intake + Market-Context reasoning agents → Input-Validator deterministic boundary) → **Knot** (Simulation Agent — deterministic, DRAPS `run_simulation`, no LLM) → **Right Wing** (Interpretation reasoning agent → Disclosure deterministic agent → optional Explanation RAG agent) → **Memory Agent** (deterministic, predicted-vs-realised loop).

The **agent-type law** governs extension: input ambiguous → reasoning agent on a wing; input structured/output knowable → deterministic agent. The knot never grows; new agents extend the wings.

---

## The full ASCII wiring diagram

```
   PROMPT  ("model tariff hedge options for this loan, file the disclosure")
      |
      v
 +----------------------------------------------------------------------+
 |  ORCHESTRATOR AGENT                          [reasoning - Gemini Pro] |
 |  Decomposes the ask; sequences agents; checkpoints; owns eval gate.   |
 |  Does no domain work. The prompt stops here - it never reaches knot.  |
 +----------------------------------------------------------------------+
      |
      |   plan + private_loan_doc
      v
  ============================ LEFT WING ============================
                          (probabilistic - reasoning)

  +-------------------------+      +----------------------------+
  | INTAKE AGENT            |      | MARKET-CONTEXT AGENT       |
  | [reasoning - Gemini]    | ---> | [reasoning - Gemini]       |
  |                         |      |                            |
  | Reads private loan doc; |      | Fetches public signals:    |
  | extracts: notional,     |      |  tariffs, Fed curve,        |
  | spread, schedule, ccy.  |      |  sovereign ratings.         |
  |                         |      |                            |
  | PRIVATE data lands here.|      | PUBLIC data lands here.    |
  +-------------------------+      +----------------------------+
            |                                  |
            +---------+   +--------------------+
                      |   |
                      v   v
        +---------------------------------------+
        | INPUT-VALIDATOR AGENT                 |
        | [DETERMINISTIC - plain code, no LLM]  |
        |                                       |
        | Schemas: types, ranges, dates align,  |
        | currencies match, rate-curve mapped.  |
        | Rejects ambiguity. ONLY producer of   |
        | `validated_inputs`.                   |
        +---------------------------------------+
                      |
                      |   validated_inputs   (clean, schema-passed)
                      v
  ============================== KNOT ==============================
                          (deterministic core)

        +---------------------------------------+
        | SIMULATION AGENT                      |
        | [DETERMINISTIC - DRAPS run_simulation]|
        |                                       |
        | Calls DRAPS run_simulation MCP tool.  |
        | No LLM. No prompt. Reproducible.      |
        | Reads ONLY validated_inputs - never   |
        | sees the prompt.                      |
        |                                       |
        | Produces simulation_result:           |
        |   A_total, B_total, C_total, events.  |
        +---------------------------------------+
                      |
                      |   simulation_result
                      v
  ============================ RIGHT WING ===========================
                       (mix - reasoning + deterministic)

        +---------------------------------------+
        | INTERPRETATION AGENT                  |
        | [reasoning - Gemini]                  |
        |                                       |
        | The "why". Reads simulation_result;   |
        | produces the recommendation:          |
        |   winner scenario, $ saving,          |
        |   cost-of-delay, rationale.           |
        +---------------------------------------+
                      |
                      v
        +---------------------------------------+
        | DISCLOSURE AGENT                      |
        | [DETERMINISTIC - ACTUS-Mentor         |
        |  /generate-xbrl-report]               |
        |                                       |
        | Produces IFRS + US-GAAP XBRL.         |
        | TWO calls: one for loan side, one for |
        | hedge side. Templating, not RAG.      |
        +---------------------------------------+
                      |
                      v
   ............................................................
   :  EXPLANATION AGENT     [OPTIONAL - off the critical path] :
   :  [reasoning - ACTUS-Mentor RAG pipeline]                  :
   :  Side assistant for follow-up "why" questions.            :
   :  This is the ONLY place ACTUS-Mentor's RAG lands.         :
   ............................................................
                      |
                      v
  ============================ FEEDBACK ============================
                          (deterministic)

        +---------------------------------------+
        | MEMORY AGENT                          |
        | [DETERMINISTIC - persistence]         |
        |                                       |
        | Stores: inputs, predicted outcome,    |
        | recommendation, audit_log.            |
        | Each quarter: compares                |
        | predicted-vs-realised, recalibrates.  |
        |                                       |
        | This is the NEW build. The only piece |
        | neither ACTUS-Mentor nor DRAPS has    |
        | today.                                |
        +---------------------------------------+
                      |
                      v
                   +------+
                   | END  |
                   +------+

  FAILURE PATH (parallel, not shown in main flow for clarity):
    INPUT-VALIDATOR -[errors AND retries < N]-> back to INTAKE
    INPUT-VALIDATOR -[errors AND retries >= N]-> GIVE-UP AGENT -> END
        (GIVE-UP returns honest failure, never a fabricated result)
```

---

## What the structure produces (not "adds")

The four enterprise walls are cleared by the *shape*, not by features bolted on:

| Enterprise wall | How the shape clears it |
|---|---|
| **Public + private data fusion** | Private data enters at Intake (left wing). Public data enters at Market-Context (left wing). Both are reconciled by the deterministic Input-Validator before reaching the knot. The two streams literally meet at the boundary. |
| **Long-running tasks** | Every node is a checkpoint. The graph is a LangGraph with `SqliteSaver`. A crashed run resumes at the failed node via `thread_id`, not from the prompt. |
| **Reasoning interweave** | Four reasoning agents (Orchestrator, Intake, Market-Context, Interpretation) consult, then a deterministic core commits. No single LLM call decides the answer. |
| **Long-term memory** | The Memory Agent's predicted-vs-realised loop. Trustworthy because the deterministic knot makes drift attributable — drift attributes to the wings, not core noise. |

---

## Why the bow-tie discipline matters

- **Efficiency**: Gemini runs on four nodes (Orchestrator, Intake, Market-Context, Interpretation). Four nodes (Input-Validator, Simulation, Disclosure, Memory) are deterministic — *free compute*. Half the graph is deterministic; LLM cost is spent only where input is genuinely ambiguous.

- **Interoperability**: ACTUS is the load-bearing wall. The knot consumes ACTUS contracts, the Disclosure agent emits ACTUS-derived XBRL. The standard is what makes the pipeline automatable rather than re-keyed.

- **Auditability**: The prompt never crosses into the knot. Knot output is reproducible from `validated_inputs` alone — a one-line graph audit. The deterministic boundary is the audit gate.

---

## The agent-type law (extension rule)

> **input ambiguous → reasoning agent on a wing**
> **input structured / output knowable → deterministic agent**
> **the knot never grows — new agents extend the wings**

Concretely, when adding future agents:

- A **Board-Memo Agent** (right wing, further out, reasoning) — narrative summary for the board pack
- A **Portfolio-Rollup Agent** (right wing, further out, deterministic) — aggregating across many loans
- A **Counterparty-Risk Agent** (left wing, further out, reasoning) — adds sovereign/credit context

Each is classified by the law before being added. The simulation knot stays exactly the contract simulation — no agent ever sits inside the deterministic core.

---

## Two structural lines (the invariants)

1. **PROMPT BOUNDARY** — only the Orchestrator and the left-wing reasoning agents ever see `prompt`. The Simulation Agent reads `validated_inputs` only. Searching the graph for nodes that read `prompt` is a one-line audit.

2. **CLEAN-INPUTS GATE** — only the Input-Validator can produce `validated_inputs`. Only the Simulation Agent consumes it. No other edge carries it. The boundary is enforced by data flow, not by convention.

---

**End of design-1-conceptual-design.md**
