# ACTUS Hedge Advisor — V2 (hedgeAdvisor2)

Bow-tie multi-agent system for autonomous supply-chain hedging.
**V2 redesign in progress.** Authoritative design: [`DESIGN/DESIGN-V1/`](DESIGN/DESIGN-V1/). Top-level signpost: [`DESIGN.md`](DESIGN.md).

The V1 system in `entAgentProject21/` remains the reference implementation. V2 extends it with configurable risk-factor profiles, hedge specs, and component formulas — see `design-v1-config-architecture.md`. Implementation proceeds in 12 vertical-slice iterations (`design-v1-iteration-plan.md`); **Iteration 1 (byte-equality replay) is the architectural gate**.

---

## Run locally

### Prerequisites
- Python 3.11+
- Node.js 20+
- A Google Gemini API key (for the reasoning agents)
- DRAPS server running on `:4000` (Node/TS, `SWAPS-interface/Backend`, started with `npm run server`)
- ACTUS engine running on `:8083` (called by DRAPS internally)
- ACTUS-Mentor backend (only needed for disclosure path; not required for byte-equality)

See `.env.example` for the full env-var list.

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

## Quick smoke test (no LLM needed)

The Option 2 wiring (collection-inline → DRAPS) has a standalone end-to-end check that doesn't require Gemini:

```bash
cd backend
python run_draps_local.py
```

This proves: DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json loads → `_build_config_data` produces the right shape → DRAPS responds → A/B/C totals are extractable. See `CHANGES-OPTION2.md` for the wiring rationale.

---

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/run` | Start a hedge analysis |
| GET | `/trace` | SSE stream of agent progress |
| POST | `/resume` | Resume a crashed run |
| GET | `/history` | List past recommendations + drift |

---

## V2 layout additions (Iteration 1+)

```
hedgeAdvisor2/
├── config/
│   ├── risk-factor-profiles/export-import/   ── per-corridor/commodity profiles
│   ├── risk-factor-components/               ── formula specs (one JSON per component)
│   └── hedge-specs/                          ── scenario shape per customer policy
├── schemas/                                  ── JSON Schemas for the above
└── backend/
    ├── profile_resolver.py        (N3a)
    ├── hedge_spec_resolver.py     (N3b)
    ├── profile_spec_validator.py  (N3c)
    ├── composer.py                (N3d — derived/supplied/derived_domestic)
    └── tests/
        ├── fixtures/v1-baseline/  ── frozen V1 outputs for byte-equality
        └── test_byte_equality_v1.py
```

The composer is the dispatch. In Iteration 1 it supports `mode: derived` with `dispatch: draps_v1` only — i.e. it stamps provenance and passes through to the existing V1 DRAPS path. Later iterations add `supplied`, `derived_domestic`, and `dispatch: v2_direct`.

---

## Architecture (one-line)

Natural-language prompt → Orchestrator (Gemini) → Left wing (Intake + Market-Context, Gemini) → Input-Validator (deterministic) → **Profile-Resolver → Hedge-Spec-Resolver → Profile-and-Spec-Validator → Composer (deterministic, the boundary)** → Simulation (deterministic, DRAPS) → Right wing (Interpretation Gemini, Disclosure deterministic) → Memory (deterministic). LangGraph checkpoints after every node; the prompt never reaches the knot.
