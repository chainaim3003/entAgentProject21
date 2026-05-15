# Project 2 — ACTUS Hedge Advisor
## design-1: Files Created on Disk (Inventory from Long FIN Agents-Team-1)

> **Source chat:** "Long FIN Agents-Team-1" (https://claude.ai/chat/a0d16ca6-e71f-4eb7-84b5-5eee99c81124)
> **Date of inventory:** 2026-05-15
> **Method:** Direct `list_directory` reads of the target folders, plus `read_text_file` to confirm which version is the LATEST/authoritative.

---

## 1. Files verified ON DISK for Project 2

Folder: `C:\SATHYA\CHAINAIM3003\mcp-servers\LEGENT-PROC\`

| File | Purpose | Status |
|---|---|---|
| `PROJECT2_BOWTIE_REFRAMED.md` | **LATEST AUTHORITATIVE VERSION.** Project 2 reframed around the bow-tie engineering law: 88% demo-to-prod failure rate, US manufacturer with import-dependent supply chain, stochastic/deterministic separation as the architectural law. Full 8-agent roster with agent-type law. Sections 1-6 + Bottom line. | ✅ EXISTS on disk |
| `PROJECT2_ACTUS_HEDGE_ADVISOR.md` | **EARLIER DRAFT — superseded.** The earlier "cross-border exporters" framing. Useful for the DRAPS evidence and the verified-from-team-record narration, but the problem statement framing is older and was replaced by BOWTIE_REFRAMED. | ✅ EXISTS on disk (but superseded) |
| `hedge_advisor_graph_skeleton.py` | LangGraph skeleton code — 5 sections (State, Nodes, Conditional Edge, Graph, Run); each node tagged `[REASONING - Gemini]` or `[DETERMINISTIC - no LLM]`; agent-type law enforced by which nodes import the Gemini client; `SqliteSaver` checkpointer; `thread_id`-based resume. Contains 3 explicit `TODO: confirm contract` markers for the unverified connector details. | ✅ EXISTS on disk |

### Other files in LEGENT-PROC (context, not Project 2 outputs from this chat)

Files present in the same folder that pre-date or were not Project-2-specific outputs of the source chat:

- `20240907_AI and Financial Analysis Risk and Core Banking Final (2).pdf` (Brammertz & Kubli paper)
- `Agentic Procurement.pptx`
- `DEMO video - agent negotiation.mp4`
- `DRAPS_Narration_Script - v1.md`
- `FULL DOCUMENTATION PROJECT OVERVIEW.docx`
- `LegentPRO-V2.mp4`
- `REVIEW_1.pptx`
- `VLEI_Documentation.docx`

---

## 2. Which file is authoritative for which content

| Content | Authoritative source on disk |
|---|---|
| **Problem statement (latest framing)** | `PROJECT2_BOWTIE_REFRAMED.md` Section 1 — demo-to-prod gap, 88% pilots fail, US manufacturer, stochastic infection |
| **Solution statement (latest)** | `PROJECT2_BOWTIE_REFRAMED.md` Section 2 — agent roster wing-by-wing |
| **Impact (latest)** | `PROJECT2_BOWTIE_REFRAMED.md` Section 3 — reusable architectural pattern, enterprise walls cleared by construction, SCF $7-8B, $41,875 DRAPS proof |
| **Conceptual design (bow-tie diagram)** | `PROJECT2_BOWTIE_REFRAMED.md` Section 4 |
| **DRAPS evidence (verified from team record)** | `PROJECT2_ACTUS_HEDGE_ADVISOR.md` Section 2 — DRAPS narration script details (kept for the verified DRAPS run details: $192,275 total interest, $41,875 saving, $17,025 cost-of-delay, GTAP Armington elasticity 3.8 textiles, etc.) |
| **LangGraph implementation skeleton** | `hedge_advisor_graph_skeleton.py` |

---

## 3. File that the source chat attempted to write but is NOT currently on disk

| File path | Status |
|---|---|
| `C:\SATHYA\CHAINAIM3003\mcp-servers\FINAGENTS\FINAGENTS1\ACTUS-MENTOR-MCP\HACKATHON_IDEATION.md` | ❌ NOT present at this path as of 2026-05-15 |

The source chat shows a `Filesystem:write_file` call to this path early in the conversation (covering Project 1, 2, 3 ideation). The file is not at that location today. Either:
- (a) It was written but later moved/deleted
- (b) The write call did not persist
- (c) It is stored in a different path

I have *not* verified which of (a)/(b)/(c) is correct.

**Note:** the BOWTIE_REFRAMED file came LATER in the same chat as a deliberate rewrite of Project 2 only — so even if `HACKATHON_IDEATION.md` were recovered, its Project 2 section would be the *older* framing and would be superseded by `PROJECT2_BOWTIE_REFRAMED.md`.

---

## 4. Files in this DESIGN1 folder (the present extraction)

Folder: `C:\SATHYA\CHAINAIM3003\mcp-servers\FINAGENTS\FINAGENTS2\entAgentProject21\DESIGN\DESIGN1\`

| File | Contents | Source on disk |
|---|---|---|
| `design-1-problem-solution-impact.md` | Spine (bow-tie + agent-type law) + Sections 1, 2, 3 of BOWTIE_REFRAMED | `PROJECT2_BOWTIE_REFRAMED.md` |
| `design-1-conceptual-design.md` | Section 4 (bow-tie ASCII diagram) + extension pattern + track fit | `PROJECT2_BOWTIE_REFRAMED.md` |
| `design-1-detailed-design.md` | N0–N8 textual graph (from chat response) + Sections 5, 6, Bottom line | `PROJECT2_BOWTIE_REFRAMED.md` + chat response |
| `design-1-files-on-disk.md` | This file — inventory of what was on disk | direct filesystem reads |

---

## 5. Cross-reference: where the originals live vs. where this extraction lives

```
SOURCE FILES (from Long FIN Agents-Team-1):
  C:\SATHYA\CHAINAIM3003\mcp-servers\LEGENT-PROC\
    ├── PROJECT2_BOWTIE_REFRAMED.md       << LATEST authoritative version
    ├── PROJECT2_ACTUS_HEDGE_ADVISOR.md   << earlier draft, superseded
    └── hedge_advisor_graph_skeleton.py   (Python — LangGraph skeleton code)

THIS EXTRACTION (clean, versioned):
  C:\SATHYA\CHAINAIM3003\mcp-servers\FINAGENTS\FINAGENTS2\entAgentProject21\DESIGN\DESIGN1\
    ├── design-1-problem-solution-impact.md   (from BOWTIE_REFRAMED §1, 2, 3)
    ├── design-1-conceptual-design.md         (from BOWTIE_REFRAMED §4)
    ├── design-1-detailed-design.md           (chat textual graph + BOWTIE_REFRAMED §5, 6, bottom line)
    └── design-1-files-on-disk.md              (this file)
```

---

## 6. What is NOT yet on disk (and was not produced in the source chat)

For full implementation, these are still to-build:

- The actual production code (the skeleton is just the LangGraph structure with TODOs)
- The DRAPS `mcp-server.ts` connector wiring (the one remaining honest gap from the source chat)
- The Memory Agent persistence backend (the only genuinely new build)
- The `hedge_relationship` block extension for the Disclosure Agent (~30 lines)
- Tests, deployment scripts, a UI

---

## 7. Correction history of this DESIGN1 extraction

- **v1 (overwritten)**: First pass used the older "cross-border exporters" framing from `PROJECT2_ACTUS_HEDGE_ADVISOR.md`. This was incorrect — that file is the earlier draft.
- **v2 (current)**: Corrected to use `PROJECT2_BOWTIE_REFRAMED.md` (the LATEST authoritative version) for all of problem, solution, impact, and conceptual design. The textual graph in `design-1-detailed-design.md` is preserved from the source chat response (it complements the BOWTIE_REFRAMED bow-tie diagram with explicit node IDs and edges).

---

**End of design-1-files-on-disk.md**
