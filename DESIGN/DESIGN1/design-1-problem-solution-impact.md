# Project 2 — ACTUS Hedge Advisor
## design-1: Refined Problem Statement, Solution, Impact

> **Source:** Extracted from chat "Long FIN Agents-Team-1"
> (https://claude.ai/chat/a0d16ca6-e71f-4eb7-84b5-5eee99c81124)
> **Hackathon:** lablab.ai · Transforming Enterprise Through AI · Tracks 2 (Gemini) + 4 (Data & Intelligence)
> **Date extracted:** 2026-05-15

---

## 1. Refined Problem Statement

Cross-border exporters carry floating-rate trade-finance loans that run for years. Over that life, three forces — **tariff changes, central-bank rate moves, and sovereign risk shifts** — silently inflate the real cost of the loan, quarter after quarter. The exporter could neutralize this with an interest-rate swap, but deciding *whether* to hedge, *when*, and *at what rate* requires fusing three separate disciplines:

1. **Trade economics** — how tariffs pass through to cost
2. **Interest-rate modelling** — where the rate curve is heading
3. **Cash-flow simulation** — what the specific contract actually pays

Mid-market exporters almost never do this analysis — it's too specialized and too expensive to run per-loan — so they absorb avoidable losses, and their financial reporting never reflects the embedded risk they're carrying.

### Why this is an enterprise agentic-AI problem (all four enterprise walls)

A correct answer requires an agent to:

| Enterprise wall | What's required for hedge decision |
|---|---|
| **Public + private data fusion** | Public: tariff schedules, trade elasticities, Fed forward curves, sovereign ratings. Private: company's actual loan contracts and cash-flow schedules. Reasoning must interweave both without leaking. |
| **Long-running tasks** | Multi-step pipeline: ingest → model → simulate → compare → recommend → report. Must checkpoint, fail safely, and resume. |
| **Reasoning interweave** | Multiple specialist agents/models consulted and synthesized before an action commits. |
| **Long-term memory** | What was recommended, what worked, what was attested — must survive across sessions and feed back as recalibration. |

---

## 2. Refined Solution

An autonomous agent — **ACTUS Hedge Advisor** — that continuously answers, for any floating-rate trade loan:

> *"What will this loan really cost, should we hedge it, when, and what do we disclose?"*

It works because the hard pieces already exist and only need to be assembled into a standing agent:

- **Tariff-to-rate modelling + multi-scenario simulation** is what **DRAPS already does** — it has produced exact numbers on a real India→US textile loan.
- **Financial-contract representation + XBRL reporting** is what **ACTUS-Mentor already does**, live, in 12 languages.
- **ACTUS is the interoperability standard** that makes a private loan contract machine-readable in the first place — the backbone that lets the whole pipeline be automated rather than re-keyed across four systems.

### The one genuinely new build: Memory

Persisting every recommendation with its inputs and predicted outcome, then **each quarter comparing predicted-versus-realised and recalibrating**. That feedback loop is what turns a one-shot calculator into an agent that gets better.

This is the explicit answer to the "long-term memory" enterprise-agentic-AI requirement — both ACTUS-Mentor (no inter-session memory) and DRAPS (one-shot runs) lack it today.

---

## 3. Impact

### Market sizing (grounded, ranges honest)

| Layer | Size | Source/notes |
|---|---|---|
| **Underlying financing flows exposed to this risk** | ~USD 2.3T | Multiple SCF market reports |
| **Trade-finance gap** | ~USD 2.5T | WTO, ADB |
| **SCF technology market today** | ~USD 7–8B, growing high-single-digit CAGR | 360iResearch and other SCF market reports |
| **SOM (beachhead)** | India→US textiles corridor — the exact corridor DRAPS already demonstrated | Honestly framed as a beachhead, not a number. Expandable because GTAP (trade) and ACTUS (contracts) already cover other corridors and contract types. |

### Hard dollar evidence (from the DRAPS demo, not speculation)

For a single **$1M trade-finance loan**:
- **Acting early on a hedge saved $41,875**
- **Waiting three months cost $17,025**

Multiply across a typical exporter's loan book → the business case writes itself for the CFO / treasury lead.

### Pain is current and named — two grounded evidence points

1. **Exporters systematically under-hedge.** Academic study of 350 SME exporters/importers (Brisbane & Sydney — ResearchGate 346838768): "the majority of SMEs do not hedge transaction exposure, while most of those that do hedge do so selectively." The hedging literature "tends to focus on large firms" — mid-market exporters are under-served. This is the demand-side gap ACTUS Hedge Advisor fills: it makes the hedge analysis cheap enough that selective/non-hedgers can act.
   - *Honest caveat:* The SME-hedging study is Australian and not new; treat it as indicative of a well-known pattern, not as proof of the exact size of the gap today.

2. **Tariffs are a current, named cost driver.** 360iResearch's SCF market report states plainly that 2025 US tariff introductions "precipitated a cascade of effects across global trade corridors" and that companies are "seeking alternative financing structures to mitigate the impact of elevated duties." The DRAPS demo models exactly this — a textile loan whose rate peaks at 10.34% when the tariff hits its 60% ceiling.

### Who buys it (the enterprise buyer is named, not abstract)

- **CFO** of a mid-market exporter
- **Treasury lead** / treasurer
- **Trade-finance officer** at the lending bank (secondary buyer — bank can offer this to its SME clients as a service)

### Track fit (lablab.ai hackathon)

- **Track 2 (Gemini):** Gemini Pro is the reasoning engine on the orchestrator and all wing reasoning agents.
- **Track 4 (Data & Intelligence):** public/private multi-source data fusion producing decision-support intelligence.
- **Track 1 (Veea/Security):** *not* claimed — would be dishonest to force a fit.

---

## 4. Why this framing is the right one

It is neither academic nor a sales deck, because the **bow-tie is an engineering law with a dollar consequence** — and it is the same law the enterprise-AI field is converging on in 2026 under "deterministic guardrails." The three properties enterprises screen for — efficiency, interoperability, auditability — are not features added to this design; they are what the stochastic/deterministic separation *produces*, expressed as a multi-agent wiring diagram.

Project 2 is the application of that law to agentic AI, demonstrated on a real supply-chain loan, with an open interoperability standard (ACTUS) as the load-bearing wall.

---

## 5. The honest caveats carried forward

These remain *connector* details, not architecture risks:

1. **DRAPS `run_simulation` MCP tool input/output contract** — needs the `mcp-server.ts` read in the GitHub repo's `SWAPS-interface/Backend/` (not on local disk; the local `ACTUS-LOCAL-EXT` path is the ACTUS engine, not the DRAPS MCP wrapper).
2. **ACTUS-Mentor `/generate-xbrl-report` endpoint** — assumed to be a deterministic templating path (not the 7-agent RAG graph). Needs confirming by reading ACTUS-Mentor's `api_server.py` (on local disk). If that endpoint actually invokes the 7-agent graph, the Disclosure Agent classification must be revisited.
3. **ACTUS-Mentor backend liveness** — frontend at 52.73.253.140 is confirmed serving; FastAPI backend on :8000 needs a direct liveness check.
4. **Brammertz/Kubli Figures 1 and 2** — the bow-tie structure here is reconstructed from the paper's prose description of each figure. The figure images were not extracted from the PDF — confirm against originals if used verbatim. The paper describes the converge-knot-fan structure but does not use the word "bow-tie"; the term is corroborated by a separate ACTUS source (researchfeatures.com).

---

**End of design-1-problem-solution-impact.md**
