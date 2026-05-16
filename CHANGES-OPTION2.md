# CHANGES — Option 2: Inline Collection Contract

**Date:** 2026-05-16
**Scope:** wire `entAgentProject21` to ship `SWAPS-1LOAN-WHAT-IF-DEMO.json` content inline to DRAPS, so the file lives inside entAgent (single source of truth) and DRAPS never reads it from its own disk.

---

## What was changed

### 1. New file: `entAgentProject21/DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json`

The Postman collection (36 KB). Copied verbatim from the DRAPS repo root. This is now the **single source of truth** — edit it here, nowhere else.

### 2. `entAgentProject21/backend/draps_client.py`

Three localised edits:

1. Added `import json` and `from pathlib import Path` at the top.
2. Added `_COLLECTION_PATH` constant and `_load_collection_content()` helper that reads `DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json`. Raises `FileNotFoundError` if missing — honest failure, no silent fallback.
3. In `_build_config_data()`, read the file and add the full parsed content under `config_metadata.collection_inline` in the request body. `collection_file` is kept as a label for DRAPS-side logging only.

### 3. `DRAPS/.../SWAPS-interface/Backend/src/routes/simulation.routes.ts`

One localised edit in the `POST /api/simulate` handler:

```typescript
const baseCollection = configData.config_metadata.collection_inline
  ?? await loadCollection(configData.config_metadata.collection_file);
```

Backward-compatible: if `collection_inline` is absent the route still falls back to `loadCollection()` (disk read) for legacy callers.

Plus one extra `console.log` line that prints `Inline mode: true/false` so you can see at a glance which path was taken.

### 4. New file: `DRAPS/.../Backend/config/stimulation/stablecoin/jurisdictions/us-genius.json`

`loadConfig()` (separate from `loadCollection()`) still reads the jurisdiction file from DRAPS disk at `config/stimulation/stablecoin/jurisdictions/`. That folder didn't exist (the on-disk layout is `config/stablecoin/jurisdictions/`, missing the `stimulation/` prefix that the code looks for). Created the expected folder tree and placed a copy of `us-genius.json` there.

This is the **only** disk read DRAPS still does for this request — and it's a parameter file that rarely changes. If you want to inline the jurisdiction too later, both sides need a similar small patch (~5 lines each).

---

## What this does NOT change

- DRAPS still calls the ACTUS engine at `http://127.0.0.1:8083/eventsBatch` from within its own logic. That is internal to DRAPS, untouched.
- `entAgentProject21`'s LangGraph wiring, validator, memory store — all untouched.
- The `tariff_current == tariff_peak` flat-tariff limitation (draps_client.py line ~105 comment) is unchanged. Your demo's 50%→60% escalation still requires N2 (`reasoning_agents.market_context_node`) to emit them separately.

---

## How to run

```powershell
# 1. Rebuild DRAPS TypeScript (one time after this change)
cd "C:\SATHYA\CHAINAIM3003\mcp-servers\DRAPS\Swaps-for-Supply-Chain-Finance\SWAPS-interface\Backend"
npm run build

# 2. Start ACTUS engine (must be listening on :8083 — separate process, not changed by Option 2)

# 3. Start DRAPS
npm run server     # listens on http://localhost:4000

# 4. (separate terminal) Start ACTUS-Mentor if you need the disclosure path
#    uvicorn api_server:app --port 8001

# 5. (separate terminal) Start entAgent backend
cd "C:\SATHYA\CHAINAIM3003\mcp-servers\FINAGENTS\FINAGENTS2\entAgentProject21\backend"
.venv\Scripts\activate
python -m main      # listens on http://localhost:8000

# 6. (separate terminal) Start frontend
cd "C:\SATHYA\CHAINAIM3003\mcp-servers\FINAGENTS\FINAGENTS2\entAgentProject21\frontend"
npm run dev         # listens on http://localhost:5173
```

---

## Verification

When you trigger a run, the DRAPS server log should show:

```
🎯 Config-Based Simulation Request
   Config ID: hedge-advisor-1000000.0-tex
   Collection: SWAPS-1LOAN-WHAT-IF-DEMO.json
   Inline mode: true         ← this confirms Option 2 is active
   ✅ Config resolved
   Jurisdiction: US-GENIUS
   ✅ Base collection loaded
   Collection name: SWAPS-1LOAN What-If-3-INP: India-US (tex/pha/oil)
   Operations: 4
   🚀 Running ACTUS simulation...
   ✅ Simulation complete
```

If `Inline mode: false` appears, entAgent didn't ship the inline content — check that `DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json` is at the expected path and the Python edits in `draps_client.py` are present.

---

## Rollback

To revert: delete `collection_inline` from the request body in `_build_config_data()` and remove the `?? await loadCollection(...)` clause's left-hand side (keep just `loadCollection(...)`). Or `git revert` the commits that introduced these three changes.
