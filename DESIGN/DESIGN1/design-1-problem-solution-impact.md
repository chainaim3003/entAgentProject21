# Project 2 — ACTUS Hedge Advisor
## design-1: Refined Problem Statement, Solution, Impact

> **Source:** `C:\SATHYA\CHAINAIM3003\mcp-servers\LEGENT-PROC\PROJECT2_BOWTIE_REFRAMED.md`
> from chat "Long FIN Agents-Team-1" (https://claude.ai/chat/a0d16ca6-e71f-4eb7-84b5-5eee99c81124)
> **This file content is verbatim from Sections 1, 2, 3 of the BOWTIE_REFRAMED file (the latest authoritative version).**
> **Date extracted:** 2026-05-15
> **Hackathon:** Transforming Enterprise Through AI · Primary tracks: 2 (Gemini) + 4 (Data & Intelligence)

---

## The spine: the bow-tie, and the agent-type law

Brammertz & Kubli argue from first principles that finance has exactly two problem spaces, and they must never be confused:

- **The stochastic space** — risk factors: market (tariffs, rate curves, FX), credit, behavioral. "Stochastic and difficult to forecast."
- **The deterministic space** — the financial contract: "mathematically defined agreements and therefore deterministic." Given the risk-factor state, the contract's events and cash flows "become a deterministic exercise."

Drawn out, this is the bow-tie: stochastic risk factors **converge in** to the deterministic contract (the knot), the contract produces exact state-contingent cash flows, and the analysis **fans out** — liquidity, valuation, IFRS reporting, scenario comparison.

The paper's punchline is an engineering law: **AI belongs on the two stochastic wings** (forecasting inputs, interpreting outputs); **AI must not touch the deterministic knot** — putting a probabilistic model where a deterministic algorithm belongs is "a stupid application of AI," slower and costlier than a computation knowable a priori. Ignore the law and "even the deterministic elements get stochastically infected" — you lose auditability.

**This project turns that law into a multi-agent architecture.** Every node is an agent with a uniform orchestration interface (structured input, structured output, individually testable). But agent *type* is a deliberate per-node choice:

- **Reasoning agents** (Gemini) live ONLY on the wings — they handle ambiguity, extraction, interpretation.
- **Deterministic agents** (plain code or existing MCP tools — no LLM inside) live in and around the knot — they run contracts, validate schemas, build structured documents, persist records.

The orchestration is uniform; the internals respect the stochastic/deterministic split. Prompts drive the wings; prompts never reach the knot.

---

## 1. Problem Statement

The 2026 enterprise-AI picture is blunt: agents are embedded by default, but the demo-to-production gap is where most of them die — the widely-cited figure is that roughly **88% of agent pilots never reach production**, and the failures cluster not on model quality but on scoping, evals, and governance. The root architectural cause, in enterprise finance specifically, is that teams **put the probabilistic engine in the wrong place** — they let an LLM do work a deterministic algorithm should own, or fuse private and public data with no standard between them, and the deterministic core gets *stochastically infected*. The result is the thing every enterprise buyer rejects on sight: an agent that is confident, fast, has no **decision provenance** for compliance, and no efficiency case either — it burns expensive probabilistic compute to approximate answers a deterministic contract could produce exactly, for free.

Supply-chain tariff hedging is where this failure gets concrete, expensive, and current. A US manufacturer carries a floating-rate working-capital loan financing an import-dependent supply chain. Over the loan's life, two stochastic forces — tariff escalation on imported inputs, and central-bank rate moves — compound: tariffs raise cost of goods, rate moves raise cost of capital. The manufacturer could neutralize the rate exposure with an interest-rate swap, but the decision is exactly the kind of **long-horizon, multi-step agentic workflow** that breaks in production: it must fuse **public stochastic data** (tariff schedules, trade elasticities, rate curves) with the **private deterministic contract** (the company's actual loan); it runs a multi-step pipeline where a single failed tool call kills the run; it must **interweave reasoning** across trade economics, rate modelling, and cash-flow simulation; and to be trustworthy quarter after quarter it needs **memory** — what it recommended last cycle and whether reality agreed. Today this is done with spreadsheets and a treasurer's intuition: slow, per-loan, rarely, and impossible to audit consistently across a loan book.

Those four failure modes — public/private data fusion, long-running orchestration, reasoning interweave, long-term memory — are not hedging problems. They are *the* production walls for agentic AI in any enterprise function. Hedging just raises all four at once, on a problem with a hard dollar answer, which makes it the right place to prove a pattern rather than ship a point solution. And the reason teams keep hitting the walls is the reason Brammertz identifies from first principles: no clean separation between the stochastic and the deterministic — and, consequently, no discipline about which parts of a multi-agent system are allowed to be probabilistic.

---

## 2. Solution Statement

**ACTUS Hedge Advisor** — a prompt-driven, bow-tie multi-agent system. A natural-language ask enters at an orchestrator; the work flows out along the two stochastic wings and through the deterministic knot; every node is an agent, but agent *type* is chosen by the Brammertz law. The result is a system where the separation of probabilistic from deterministic is not a principle written in a doc — it is the wiring diagram.

**The agent roster, wing by wing:**

**LEFT WING — stochastic inputs (reasoning agents + a deterministic gate):**
- **Intake Agent** *(Gemini)* — takes the natural-language ask plus the private loan document and produces the structured primary inputs the deterministic core expects. This is where **private data enters**.
- **Market-Context Agent** *(Gemini)* — resolves the **public data**: which GTAP commodity code, which corridor, sanity-checks the tariff assumptions against public schedules.
- **Input-Validator Agent** *(deterministic — plain code, no LLM)* — schema-checks every input: ranges, types, dates. This is the **boundary**: nothing reaches the knot that is not schema-clean. If a wing's Gemini extraction hallucinated a tariff of 5.0 instead of 0.50, the validator catches it here, before it can infect a deterministic simulation.

**THE KNOT — the deterministic core (deterministic agent, no LLM, by law):**
- **Simulation Agent** *(deterministic — wraps the existing DRAPS `run_simulation` MCP tool)* — runs the GTAP derivation, builds the PAM + SWAPS ACTUS contracts, executes them against the ACTUS `:8083` engine, returns the A/B/C scenario totals. Verified from the DRAPS demo file: this is deterministic templating and computation — it builds contracts from structured inputs with JavaScript, not with an LLM, and the loan is already USD-denominated. Exact. Reproducible. Prompt-independent: change the prompt wording entirely and, given the same validated inputs, the knot's output is identical.

**RIGHT WING — stochastic outputs (reasoning + deterministic):**
- **Interpretation Agent** *(Gemini)* — turns the A/B/C results into a recommendation and the "why": which scenario wins, the cost of delay, what drove it.
- **Disclosure Agent** *(deterministic — wraps ACTUS-Mentor's XBRL report generation)* — produces the IFRS / US-GAAP-shaped disclosure document from the cash flows. Document generation from a fixed taxonomy is deterministic templating, not retrieval-reasoning — so by the bow-tie law it is a deterministic agent. [Interface unverified — see design-1-detailed-design.md Section 6, note 2.]
- **Explanation Agent** *(reasoning — ACTUS-Mentor's RAG pipeline)* — OPTIONAL, off the critical path. ACTUS-Mentor's 7-agent RAG pipeline answers ACTUS-standard questions grounded in the standard ("why does this rate-reset clause behave this way?"). It is a side assistant feature, not a load-bearing part of the hedge pipeline — included honestly as what it is, not overclaimed as the reporting engine.

**MEMORY — closing the loop (deterministic agent):**
- **Memory Agent** *(deterministic — persistence)* — stores {inputs, A/B/C result, recommendation, predicted cash-flow path}. Next cycle it compares predicted-versus-realised and surfaces the drift. Because the knot is deterministic, the comparison is exact and auditable — drift attributes cleanly to the stochastic wings, never to noise in the core.

**ORCHESTRATOR — the conductor (reasoning agent):**
- **Orchestrator Agent** *(Gemini Pro)* — decomposes the prompt into a plan, sequences the agents, checkpoints after each step, owns the eval gate. It does no domain work itself. The prompt influences what the wings extract and how they interpret — it never reaches the knot.

This is "transforming enterprise finance with AI" stated as architecture: probabilistic agents where the world is probabilistic, deterministic agents where the contract is deterministic, a validator as the boundary between them, and an open contract standard (ACTUS) as the interoperable language the two halves meet in.

---

## 3. Impact

**The deliverable is a reusable architectural pattern, not a one-off tool.** The bow-tie multi-agent shape — reasoning agents on the wings, deterministic agents at the knot, a validator boundary, a memory loop — transfers to any agentic financial workflow: loan origination, balance-sheet forecasting, regulatory reporting. It transfers because each enterprise property is *structural*, not bolted on. That is the answer to why 88% of pilots fail: they bolt governance and grounding on at the end; this builds them into the wiring.

**How the design clears every enterprise wall — by construction:**

- **Demo→prod gap** — the deterministic agents, the validator boundary, and the eval gate *are* the architecture; nothing is added at the end.
- **Public + private data** — private data enters at the Intake Agent, public data at the Market-Context Agent; they fuse only at the knot, through the ACTUS standard — one interoperable language, not brittle glue.
- **Long-running tasks** — the Orchestrator checkpoints after each agent; a failed simulation call resumes at the Simulation Agent, not from the prompt.
- **Evals** — two cheap layers, both made tractable by the split: **(1)** deterministic-core regression — the knot is reproducible, so a fixed input set must always yield the same A/B/C totals; any drift is a real bug, not noise. **(2)** wing evals — golden-set tests on the Intake Agent (NL → correct structured inputs) and Interpretation Agent (results → correct winner). Because the knot is deterministic, the wings can be evaluated *in isolation* — the hardest part of agent evals, made tractable by the architecture.
- **Auditability / decision provenance** — every agent logs {input, output}; the knot's output is reproducible from its input; any recommendation traces the full chain: prompt → extracted inputs → validated inputs → exact simulation → interpretation.
- **Efficiency** — Gemini runs on four nodes (orchestrator + three wing reasoning agents); the other four are free deterministic compute. No LLM cost spent running a contract or building an XBRL document.
- **Long-term memory** — the Memory Agent's predicted-vs-realised loop, trustworthy because the deterministic core makes drift attributable.

**The proving ground is real and currently painful.** The supply-chain-finance technology and solutions market sits at roughly USD 7–8 billion today across the majority of third-party sources (360iResearch ~USD 7.04B 2024; Expert Market Research ~USD 7.57B 2024; IMARC ~USD 8.1B 2025; Market Research Future ~USD 7.73B 2024 — one outlier, DataM, materially lower), growing high-single-digit CAGR. Underlying financing flows are far larger — WTO/IFC figures cited by Expert Market Research put global supply-chain finance at ~USD 2.3 trillion, against a trade-finance gap of ~USD 2.5 trillion. Every supply-chain-finance market report cites 2025 US tariff escalation as actively reshaping demand. The serviceable wedge is concrete — US manufacturers with import-dependent, tariff-exposed supply chains — and expandable, because GTAP covers other commodities and corridors and ACTUS represents any contract type.

**The value has a hard number behind it.** The DRAPS engine, on a $1M floating-rate loan exposed to a tariff-stressed corridor, showed hedging early saving $41,875 against the no-hedge baseline, and waiting three months costing $17,025. The pitch leads with the architecture and uses the dollars as proof.

**Honesty on SOM:** no defensible captured-market dollar figure — SOM is framed as a beachhead, a real, reachable, currently-stressed segment, not a number.

---

**End of design-1-problem-solution-impact.md**
