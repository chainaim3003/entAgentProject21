# ACTUS Hedge Advisor

Bow-tie multi-agent system for autonomous supply-chain hedging.
See full design in `DESIGN/DESIGN1/`.

---

## Run locally

### Prerequisites
- Python 3.11+
- Node.js 20+
- A Google Gemini API key (for the reasoning agents)
- Network access to DRAPS MCP server and ACTUS-Mentor backend (see `.env.example`)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and fill in GEMINI_API_KEY, DRAPS_MCP_URL, ACTUS_MENTOR_URL
python -m main
```

Backend serves on `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend serves on `http://localhost:5173`.

---

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/run` | Start a hedge analysis |
| GET | `/trace` | SSE stream of agent progress |
| POST | `/resume` | Resume a crashed run |
| GET | `/history` | List past recommendations + drift |

---

## Open contracts (NotImplementedError until verified)

Per `DESIGN/DESIGN1/design-1-detailed-design.md` §6, three external contracts remain unverified. The corresponding code points raise `NotImplementedError` with the design-doc reference — no mocks, no fallbacks.

1. `backend/draps_client.py` — DRAPS `run_simulation` MCP tool input/output shape
2. `backend/actus_mentor_client.py` — ACTUS-Mentor `/generate-xbrl-report` request/response
3. `backend/explanation_agent.py` — ACTUS-Mentor RAG pipeline endpoint

Once verified, fill in the bodies of those three modules. Nothing else changes.

---

## Architecture (one-line)

Natural-language prompt → Orchestrator (Gemini) → Left wing (Intake + Market-Context, Gemini) → Input-Validator (deterministic, the boundary) → Simulation (deterministic, DRAPS) → Right wing (Interpretation Gemini, Disclosure deterministic) → Memory (deterministic). LangGraph checkpoints after every node; the prompt never reaches the knot.
