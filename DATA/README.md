# DATA — Demo Inputs for Hedge Advisor

This folder contains sample inputs constructed **in sync with the backend**
agent schemas. Every field that N1 Intake (in `backend/reasoning_agents.py`)
expects to extract is present in these documents.

## Files

| File | Purpose |
|---|---|
| `sample-loan-agreement.txt` | Long-form loan agreement for the **loan_doc** field. Mirrors a real bank loan agreement (party names, sections, governing law). |
| `demo-prompts.md` | A library of 7 prompts (5 happy-path, 2 stress tests). Each one engineered so all 7 N1 Intake fields are extractable. Includes prompt injection and honest-failure tests. |

## Cross-reference — fields N1 Intake extracts

Per `backend/reasoning_agents.py` (N1 INTAKE_SCHEMA):

| Field | Where to find in `sample-loan-agreement.txt` |
|---|---|
| `notional_usd` | Section 1: USD 1,000,000 |
| `spread_bps` | Section 2: SOFR + 250 basis points |
| `term_months` | Section 3: 24 months |
| `start_date` | Section 3: January 15, 2026 |
| `rate_index` | Section 2: SOFR |
| `commodity_hint` | Section 5: woven textile fabric imports from India |
| `corridor_hint` | Section 5: India → United States |

If you change the loan agreement, make sure all 7 fields remain extractable —
otherwise N3 Validator will reject the extraction and the run will fail.

## Quick start

In the Hedge Advisor UI (`http://localhost:5173`):

1. Paste contents of `sample-loan-agreement.txt` into the **Private loan document** field
2. Paste Prompt 1 from `demo-prompts.md` into the **Ask** field (the question after "Should we...")
3. Click Run
4. Watch all 8 agents stream
