# Project 2 — ACTUS Hedge Advisor
## design-1: Conceptual Design + Textual Visual Diagram

> **Source:** `C:\SATHYA\CHAINAIM3003\mcp-servers\LEGENT-PROC\PROJECT2_BOWTIE_REFRAMED.md` Section 4
> from chat "Long FIN Agents-Team-1" (https://claude.ai/chat/a0d16ca6-e71f-4eb7-84b5-5eee99c81124)
> **This file content is verbatim from the BOWTIE_REFRAMED file (the latest authoritative version).**
> **Date extracted:** 2026-05-15

---

## 4. Conceptual Design

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
      +--> LEFT WING --------- stochastic inputs -------------------------+
      |   +---------------------------------------------------------------+
      |   | INTAKE AGENT                 [reasoning - Gemini]             |
      |   | NL ask + private loan doc -> structured primary inputs        |
      |   | >> PRIVATE data enters here                                   |
      |   +---------------------------------------------------------------+
      |   | MARKET-CONTEXT AGENT         [reasoning - Gemini]             |
      |   | Resolves GTAP commodity code, corridor, tariff sanity-check   |
      |   | >> PUBLIC data enters here                                    |
      |   +---------------------------------------------------------------+
      |   | INPUT-VALIDATOR AGENT        [DETERMINISTIC - plain code]     |
      |   | Schema / range / type / date checks. THE BOUNDARY.            |
      |   | Nothing reaches the knot that is not schema-clean.            |
      |   +---------------------------------------------------------------+
      |
      +--> KNOT --------------- deterministic core -----------------------+
      |   +---------------------------------------------------------------+
      |   | SIMULATION AGENT     [DETERMINISTIC - DRAPS run_simulation]   |
      |   | GTAP derivation -> builds PAM + SWAPS contracts ->            |
      |   | runs ACTUS :8083 -> A/B/C scenario totals.                    |
      |   | NO LLM. Exact. Reproducible. Prompt-independent.              |
      |   | >> deterministic + interoperable + auditable + efficient      |
      |   +---------------------------------------------------------------+
      |
      +--> RIGHT WING --------- stochastic outputs -----------------------+
      |   +---------------------------------------------------------------+
      |   | INTERPRETATION AGENT         [reasoning - Gemini]             |
      |   | A/B/C results -> recommendation + the "why" + cost-of-delay   |
      |   +---------------------------------------------------------------+
      |   | DISCLOSURE AGENT     [DETERMINISTIC - ACTUS-Mentor XBRL gen]  |
      |   | Cash flows -> IFRS / US-GAAP disclosure document.             |
      |   | Templating from a fixed taxonomy = deterministic, not RAG.    |
      |   +---------------------------------------------------------------+
      |   | EXPLANATION AGENT    [reasoning - ACTUS-Mentor RAG pipeline]  |
      |   | OPTIONAL / off critical path. Answers ACTUS-standard          |
      |   | questions, grounded. A side assistant feature.                |
      |   +---------------------------------------------------------------+
      |
      +--> MEMORY AGENT                 [DETERMINISTIC - persistence]-----+
          Stores {inputs, A/B/C result, recommendation, predicted path}.
          Next cycle: predicted vs realised -> drift, recalibrate.
          Exact + auditable, because the knot is deterministic.

   AGENT-TYPE LAW:  input ambiguous?  -> reasoning agent, lives on a wing.
                    input structured, output knowable?  -> deterministic agent.
                    The knot never grows. New agents extend the wings.
```

---

## Extending the system — "further left / further right"

The pattern extends cleanly. Further left, more input agents (a live Tariff-Feed Agent pulling WTO/PIIE data; a Sovereign-Rating Agent) — all reasoning agents, all feeding the same Input-Validator boundary. Further right, more output agents (a Board-Memo Agent; a Portfolio-Rollup Agent across many loans) — a mix of reasoning and deterministic. The rule for any new agent is the agent-type law above. The knot never grows; it stays exactly the contract simulation.

---

## Track fit

Track 2 (Gemini is the reasoning engine on the orchestrator and all wing reasoning agents) and Track 4 (public/private multi-source data fusion producing decision-support intelligence). Track 1 is not a genuine fit and is not claimed.

---

**End of design-1-conceptual-design.md**
