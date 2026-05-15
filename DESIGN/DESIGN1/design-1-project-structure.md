# Project 2 — ACTUS Hedge Advisor
## design-1: Project Structure (Backend + Frontend with NL Interface)

> **Source:** Authored 2026-05-15, aligned with `design-1-problem-solution-impact.md`,
> `design-1-conceptual-design.md`, `design-1-detailed-design.md` in this same folder.
> **Pattern reference:** ACTUS-Mentor MCP (`C:\SATHYA\CHAINAIM3003\mcp-servers\FINAGENTS\FINAGENTS1\ACTUS-MENTOR-MCP\`)
> — the team's existing FastAPI + React + LangGraph project, used as the structural reference.
>
> **Status:** Design only. No code created. No mocks, no hardcoding, no fallbacks anywhere in the proposed implementation.

---

## 1. Design philosophy (anti-proliferation rules)

1. **One file per concept, not per class.** All reasoning agents in one file; all deterministic agents in one file. The agent-type law becomes literally visible in the import structure of each file.
2. **Don't split until pain demands it.** A single `schemas.py` is fine until it grows past ~300 lines.
3. **Mirror ACTUS-Mentor's familiar shape** so the team can navigate it without learning a new layout.
4. **No layer that only forwards.** If a "service" layer just wraps a client one-to-one, it's deleted — the client is the service.
5. **Tests grouped by zone**, not per file. `test_knot.py` covers everything deterministic; `test_wings.py` covers everything stochastic.

---

## 2. Architecture at a glance

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (React + Vite, port 5173)                              │
│  • ChatPanel: natural language input + live agent trace          │
│  • ResultsPanel: A/B/C scenarios + recommendation + disclosure   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/SSE (streaming agent trace)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI backend (port 8000)                                     │
│  • POST /run    — start a hedge analysis                         │
│  • GET  /trace  — server-sent events: live agent progress        │
│  • POST /resume — resume a crashed run by thread_id              │
│  • GET  /history — past recommendations + drift                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  LangGraph workflow (8 agents + Give-Up, one shared State)       │
│  • Reasoning agents → Gemini SDK                                 │
│  • Simulation agent → DRAPS run_simulation MCP                   │
│  • Disclosure agent → ACTUS-Mentor /generate-xbrl-report HTTP    │
│  • Memory agent → local persistence (swap backend in one line)   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Folder tree

```
hedge-advisor/                          ← repo root
│
├── README.md                           1 file
├── DESIGN.md                           1 file   (in-repo design summary; full design lives in DESIGN1/)
├── .gitignore                          1 file
├── docker-compose.yml                  1 file   (one-command local startup: backend + frontend)
│
├── backend/                            ─────────
│   │
│   ├── main.py                         1 file   FastAPI app, lifespan, route registration
│   ├── api.py                          1 file   All 4 routes (/run, /trace, /resume, /history) + Pydantic schemas
│   ├── config.py                       1 file   All env vars: GEMINI_API_KEY, DRAPS_MCP_URL, ACTUS_MENTOR_URL, CHECKPOINT_DB_URL, MEMORY_DB_URL
│   │
│   ├── graph.py                        1 file   HedgeAdvisorState (TypedDict) + build_graph() + route_after_validator
│   │
│   ├── reasoning_agents.py             1 file   N0 Orchestrator, N1 Intake, N2 Market-Context, N5 Interpretation (all import Gemini)
│   ├── deterministic_agents.py         1 file   N3 Validator, N4 Simulation, N6 Disclosure, N8 Memory, NX Give-Up (no Gemini import — agent-type law enforced by file)
│   ├── explanation_agent.py            1 file   N7 — optional RAG side assistant (separate because off the critical path)
│   │
│   ├── gemini_client.py                1 file   Gemini SDK wrapper, structured-output schemas
│   ├── draps_client.py                 1 file   MCP client for run_simulation tool
│   ├── actus_mentor_client.py          1 file   HTTP client for /generate-xbrl-report
│   ├── memory_store.py                 1 file   Pluggable: SQLite for dev, swap to Postgres in 1 line
│   │
│   ├── requirements.txt                1 file
│   ├── .env.example                    1 file
│   │
│   └── tests/
│       ├── test_knot.py                1 file   Deterministic-core regression: Validator + Simulation produce identical output for identical input
│       └── test_wings.py               1 file   Golden-set evals: Intake extraction, Interpretation choice on canned simulation results
│                                       ─────────
│                                       Backend subtotal: 15 files
│
└── frontend/                           ─────────
    │
    ├── package.json                    1 file
    ├── vite.config.ts                  1 file
    ├── tsconfig.json                   1 file
    ├── index.html                      1 file
    │
    └── src/
        ├── main.tsx                    1 file   Vite entry
        ├── App.tsx                     1 file   Layout: left=ChatPanel, right=ResultsPanel
        ├── api.ts                      1 file   All 4 backend endpoints + SSE stream parsing
        ├── ChatPanel.tsx               1 file   Natural-language input + live agent trace
        ├── ResultsPanel.tsx            1 file   A/B/C scenario table + recommendation + collapsible disclosure (XBRL) viewer + history
        └── index.css                   1 file   Single stylesheet; no CSS-in-JS proliferation
                                        ─────────
                                        Frontend subtotal: 10 files

ROOT SUBTOTAL: 4 files
BACKEND SUBTOTAL: 15 files
FRONTEND SUBTOTAL: 10 files
──────────────────────────────────────
GRAND TOTAL:    29 files
```

---

## 4. Backend file-by-file purpose

| File | Purpose | Estimated lines |
|---|---|---|
| `main.py` | FastAPI app entry, mounts `api.py` router, lifespan handler for clients (DRAPS MCP, ACTUS-Mentor HTTP) | ~50 |
| `api.py` | 4 routes + Pydantic request/response schemas (combined intentionally — they always change together) | ~200 |
| `config.py` | Reads env vars via Pydantic Settings; validates on startup. NO defaults for required values — fail fast if missing. | ~50 |
| `graph.py` | Defines `HedgeAdvisorState`; `build_graph()` wires nodes + edges; conditional routing function `route_after_validator` | ~120 |
| `reasoning_agents.py` | 4 nodes (N0, N1, N2, N5), each ~30 lines: build prompt → call Gemini with structured output → return state delta | ~150 |
| `deterministic_agents.py` | 5 nodes (N3, N4, N6, N8, NX); Validator is heaviest (~80 lines of schema rules); others ~20-40 each. **No Gemini import anywhere in this file** — agent-type law enforced by file structure. | ~250 |
| `explanation_agent.py` | Off-critical-path RAG node (N7); wraps ACTUS-Mentor's existing RAG endpoint. Kept separate because it doesn't participate in the main flow. | ~60 |
| `gemini_client.py` | One `extract()` and one `generate()` method with structured output schemas. Centralizes all Gemini calls so retry / timeout policy lives in one place. | ~80 |
| `draps_client.py` | MCP client connection + `run_simulation(payload) → events`. **Single source of truth for the DRAPS interface.** | ~80 |
| `actus_mentor_client.py` | `generate_xbrl_report(events, contract_info, taxonomy) → xbrl`. HTTP client. | ~50 |
| `memory_store.py` | `save(record)`, `compare(record_id, realised) → drift`. Backend pluggable: SQLite default; swap to Postgres in one line. | ~100 |
| `tests/test_knot.py` | Regression: fixed input → fixed output for Validator and Simulation. **This is what makes the knot trustworthy across releases.** | ~120 |
| `tests/test_wings.py` | Golden inputs → assertions on extraction shape (N1) / interpretation winner (N5). | ~100 |

Total backend code: **~1400 lines across 13 source files** (excluding `requirements.txt` and `.env.example`).

---

## 5. Frontend file-by-file purpose

| File | Purpose | Estimated lines |
|---|---|---|
| `main.tsx` | React mount | ~10 |
| `App.tsx` | Two-column layout, theme, top bar | ~60 |
| `api.ts` | `runHedgeAnalysis()`, `streamTrace()`, `resumeRun()`, `getHistory()` + SSE parsing | ~120 |
| `ChatPanel.tsx` | Input box + send button + agent trace list (bow-tie visual: orchestrator → left wing → validator → knot → right wing → memory) | ~250 |
| `ResultsPanel.tsx` | Scenario table + recommendation card + XBRL viewer + history list | ~280 |
| `index.css` | Single stylesheet | ~150 |

Total frontend code: **~870 lines across 6 source files** (plus 4 config files).

---

## 6. How the natural-language interface drives the backend

End-to-end sequence for one user query like *"I have a $1M floating-rate loan financing textile imports from India, 24 months, spread 250bps. Should I hedge?"*:

```
1. ChatPanel → POST /run { prompt, loan_doc, thread_id }
2. /run starts the LangGraph workflow asynchronously, returns thread_id immediately
3. ChatPanel → GET /trace?thread_id=... (Server-Sent Events stream)
4. Backend streams each agent's checkpoint as it completes:
   { node: "intake",        status: "done", duration_ms: 1200, summary: "extracted notional=$1M, ..." }
   { node: "market_context",status: "done", duration_ms: 800,  summary: "GTAP code 50, India→US corridor" }
   { node: "validator",     status: "done", duration_ms: 50,   summary: "✓ all inputs valid" }
   { node: "simulation",    status: "done", duration_ms: 3200, summary: "ran A/B/C against ACTUS :8083" }
   { node: "interpretation",status: "done", duration_ms: 1500, summary: "Hedge now: save $41,875" }
   { node: "disclosure",    status: "done", duration_ms: 700,  summary: "IFRS + US-GAAP XBRL ready" }
   { node: "memory",        status: "done", duration_ms: 30,   summary: "stored as record-xyz" }
5. ResultsPanel renders the final state: A/B/C table, recommendation, XBRL preview
6. User can ask follow-up → triggers N7 Explanation Agent (RAG) without re-running pipeline
```

The natural-language interface is just `POST /run` with a prompt. The "intelligence" is the 8-agent pipeline. The UI's job is to make the agent flow **visible** — so the user can see the bow-tie working, and trust it.

---

## 7. API surface (the entire backend contract)

| Method | Path | Purpose | Request | Response |
|---|---|---|---|---|
| POST | `/run` | Start a hedge analysis | `{ prompt: str, loan_doc: str, thread_id: str }` | `{ thread_id, status: "started" }` |
| GET | `/trace` | SSE stream of agent progress | query: `thread_id` | SSE events: `{ node, status, duration_ms, summary }` until final state |
| POST | `/resume` | Resume a crashed run | `{ thread_id }` | `{ thread_id, resuming_from_node }` |
| GET | `/history` | List past recommendations + drift | query: `limit, offset` | `[{ thread_id, ts, recommendation, predicted_saving, realised_saving, drift }, ...]` |

That's the whole API. Four endpoints.

---

## 8. State object — the persistence boundary

```python
class HedgeAdvisorState(TypedDict):
    # Inputs
    prompt: str
    private_loan_doc: str
    thread_id: str

    # Produced by N1
    raw_inputs: dict | None

    # Produced by N2
    market_context: dict | None

    # Produced by N3
    validated_inputs: dict | None
    validation_errors: list[str]
    retry_count: int

    # Produced by N4 (THE KNOT)
    simulation_result: dict | None    # { A_total, B_total, C_total, events }

    # Produced by N5
    recommendation: dict | None

    # Produced by N6
    disclosure_doc: dict | None

    # Produced by N8
    memory_record_id: str | None

    # Appended by every node (reducer = operator.add)
    audit_log: Annotated[list[dict], operator.add]
```

This entire dict is what gets checkpointed by LangGraph after every node. The checkpoint database **is** the audit trail.

---

## 9. What's deliberately NOT in this project

To keep file count down and scope honest:

- **No user authentication** — local/single-user for the hackathon. Auth is a deployment concern, not an architecture concern.
- **No multi-tenancy** — one user, one thread at a time. Concurrency comes with Postgres backend, not now.
- **No PDF parsing for loan documents** — the loan_doc is provided as text. PDF→text is a preprocessor, not part of the agent graph.
- **No real-time market data feeds** — Market-Context Agent uses public schedules at query time, not streaming feeds. Streaming is Phase 2.
- **No notification system** — Memory Agent's drift comparison runs on-demand, not on a schedule. Cron is a deployment add.
- **No CI/CD config** — left for deployment phase.
- **No separate "service" layer** — clients are the services. No `services/` folder that just wraps clients.
- **No separate logger module** — Python's stdlib logging + structured JSON output, configured in `main.py` only.

---

## 10. What needs to be verified before any code is written

Carrying forward from `design-1-detailed-design.md` Section 6 — these are the open contracts:

1. **DRAPS `run_simulation` MCP tool exact input/output shape** — needs read of `SWAPS-interface/Backend/src/mcp-server.ts` from GitHub. Determines `draps_client.py` interface.
2. **ACTUS-Mentor `/generate-xbrl-report` confirmed deterministic** — needs read of `api_server.py` on local disk. If it actually invokes the 7-agent RAG graph, Disclosure Agent classification changes (would move to a reasoning agent file).
3. **ACTUS-Mentor backend liveness on :8000** — frontend at 52.73.253.140 is up; backend port needs a direct curl check.

These are connector details. The structure above stands regardless — only the body of three client files would change based on what's read.

---

## 11. Honest constraints carried forward

- **No mocks** anywhere — every external call is a real call. If DRAPS is down, the run fails honestly via the Give-Up agent.
- **No hardcoding** — endpoints come from `config.py`; secrets from environment; loan-doc content from user input.
- **No fallbacks** — if Gemini returns malformed JSON for a structured output, the Validator catches it and retries; if retries exhaust, Give-Up terminates honestly. No "default values" papering over failures.

---

## 12. File count by deliverable type

| Type | Count | Notes |
|---|---|---|
| Python source (backend) | 11 | All business logic |
| Python tests | 2 | Knot regression + wing eval |
| Frontend source (TS/TSX) | 6 | All UI |
| Frontend config (TS/JSON/HTML) | 4 | Build tooling |
| Root config | 4 | README, DESIGN, .gitignore, docker-compose |
| Backend config | 2 | requirements.txt, .env.example |
| **TOTAL** | **29** | |

---

**End of design-1-project-structure.md**
