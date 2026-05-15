# Project 2 — ACTUS Hedge Advisor
## design-1: Files Created on Disk (Inventory from Long FIN Agents-Team-1)

> **Source:** Extracted from chat "Long FIN Agents-Team-1"
> (https://claude.ai/chat/a0d16ca6-e71f-4eb7-84b5-5eee99c81124)
> **Date of inventory:** 2026-05-15
> **Method:** Direct `list_directory` reads of the target folders, cross-checked against `write_file` calls visible in the source chat snippets.

---

## 1. Files verified ON DISK for Project 2 (Long FIN Agents-Team-1)

Folder: `C:\SATHYA\CHAINAIM3003\mcp-servers\LEGENT-PROC\`

| File | Purpose | Status |
|---|---|---|
| `hedge_advisor_graph_skeleton.py` | LangGraph skeleton — 5 sections (State, Nodes, Conditional Edge, Graph, Run); each node tagged `[REASONING - Gemini]` or `[DETERMINISTIC - no LLM]`; agent-type law enforced by which nodes import the Gemini client; `SqliteSaver` checkpointer; `thread_id`-based resume | ✅ EXISTS on disk |
| `PROJECT2_ACTUS_HEDGE_ADVISOR.md` | Main Project 2 design doc (problem/solution/impact/architecture) | ✅ EXISTS on disk |
| `PROJECT2_BOWTIE_REFRAMED.md` | Bow-tie reframing of Project 2 — 8 named agents, agent-type law, multi-agent system version | ✅ EXISTS on disk |

These three files are the **Project 2-specific outputs** that survived from that chat.

### Other files in LEGENT-PROC (context, not from Project 2 directly)

Files present in the same folder that pre-date or were not Project-2-specific outputs of the source chat:

- `20240907_AI and Financial Analysis Risk and Core Banking Final (2).pdf`
- `Agentic Procurement.pptx`
- `DEMO video - agent negotiation.mp4`
- `DRAPS_Narration_Script - v1.md`
- `FULL DOCUMENTATION PROJECT OVERVIEW.docx`
- `LegentPRO-V2.mp4`
- `REVIEW_1.pptx`
- `VLEI_Documentation.docx`

---

## 2. File that the source chat *attempted* to write but is NOT currently on disk

| File path | Status |
|---|---|
| `C:\SATHYA\CHAINAIM3003\mcp-servers\FINAGENTS\FINAGENTS1\ACTUS-MENTOR-MCP\HACKATHON_IDEATION.md` | ❌ NOT present at this path as of 2026-05-15 |

**What was meant to be in it (per source-chat content):**
- Project 1 — LegentPro: Trustworthy Autonomous Procurement
- Project 2 — ACTUS Hedge Advisor
- Project 3 — (third route)
- Hackathon framing: lablab.ai · Transforming Enterprise Through AI · Tracks 1, 2, 4
- Verified architecture of ACTUS-MENTOR-MCP (LangGraph 7-agent RAG, ChromaDB, Anthropic Claude default, MCP server with 6 tools, ACTUS reference server at 34.203.247.32:8083, XBRL parser/generator)
- Frontend: React 18 + Vite, 14 pages, 12-language i18n

**Honest read:** The source chat shows a `Filesystem:write_file` call to this path, but the file is not at that location today. Either:
- (a) It was written but later moved/deleted
- (b) The write call did not persist
- (c) It is stored in a different path

I have *not* verified which of (a)/(b)/(c) is correct — that would require either git log inspection or filesystem search beyond what was done here.

---

## 3. Files in this DESIGN1 folder (the present extraction)

Folder: `C:\SATHYA\CHAINAIM3003\mcp-servers\FINAGENTS\FINAGENTS2\entAgentProject21\DESIGN\DESIGN1\`

| File | Contents |
|---|---|
| `design-1-problem-solution-impact.md` | Refined problem statement, refined solution, impact (market sizing + DRAPS hard dollar evidence + track fit) |
| `design-1-conceptual-design.md` | Bow-tie conceptual design + the full ASCII wiring diagram + agent-type law |
| `design-1-detailed-design.md` | Textual graph of 8 agents + edges + invariants + verified external contracts + knot substructure |
| `design-1-files-on-disk.md` | This file — inventory of what was on disk from the source chat |

---

## 4. Cross-reference: where the originals live vs. where this extraction lives

```
SOURCE FILES (from Long FIN Agents-Team-1):
  C:\SATHYA\CHAINAIM3003\mcp-servers\LEGENT-PROC\
    ├── hedge_advisor_graph_skeleton.py    (Python — LangGraph skeleton code)
    ├── PROJECT2_ACTUS_HEDGE_ADVISOR.md    (main design doc)
    └── PROJECT2_BOWTIE_REFRAMED.md        (bow-tie reframing)

THIS EXTRACTION (clean, versioned):
  C:\SATHYA\CHAINAIM3003\mcp-servers\FINAGENTS\FINAGENTS2\entAgentProject21\DESIGN\DESIGN1\
    ├── design-1-problem-solution-impact.md
    ├── design-1-conceptual-design.md
    ├── design-1-detailed-design.md
    └── design-1-files-on-disk.md           (this file)
```

The DESIGN1 folder is the **clean, structured extraction** of Project 2 from that chat — the source files in LEGENT-PROC remain the working drafts.

---

## 5. What is NOT yet on disk (and was not produced in the source chat)

For full implementation, these are still to-build:

- The actual production code (the skeleton is just the LangGraph structure with TODOs)
- The DRAPS `mcp-server.ts` connector wiring (the one remaining honest gap from the source chat)
- The Memory Agent persistence backend (the only genuinely new build)
- The `hedge_relationship` block extension for the Disclosure Agent (~30 lines)
- Tests, deployment scripts, a UI

---

**End of design-1-files-on-disk.md**
