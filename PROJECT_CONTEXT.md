# hedgeAdvisor2 — PROJECT_CONTEXT

> **Authoritative ground-truth file for this project.** Read this first when starting any new chat session on hedgeAdvisor2. Update it at the end of each shipped iteration (per `design-v1-iteration-plan.md` §5).

---

## 1. What this project is

hedgeAdvisor2 is the **V2 redesign** of the ACTUS-based Hedge Advisor. The goal is to take the working V1 demo (India-US textiles, one corridor, one commodity) and generalise the architecture to **any corridor / any commodity / any mode** (`derived`, `supplied`, future `domestic_*`) **without breaking the V1 numbers**. The lock is byte-equality: V2 must reproduce V1's SOFR path, swap fixed rates, and A/B/C totals exactly. Every iteration adds capability and keeps the byte-equality test green.

The architecture is the LangGraph "bow-tie" inherited from V1, extended with five new deterministic nodes (`N3a` Profile-Resolver, `N3b` Hedge-Spec-Resolver, `N3c` Profile-and-Spec-Validator, `N3d` Composer, `N6a` Provenance) per `design-v1-detailed-design.md §1`. Configuration is a three-layer JSON merge (`_base.json` -> corridor -> commodity) per `design-v1-config-architecture.md §4`.

---

## 2. Repo layout (only the parts you'll touch)

```
hedgeAdvisor2/
+- backend/                              # Python / FastAPI / LangGraph
|  +- api.py                             # FastAPI surface; RunRequest.supplied (Iter-3)
|  +- graph.py                           # LangGraph wiring; HedgeAdvisorState
|  +- composer.py                        # N3d; derived + supplied dispatch
|  +- profile_resolver.py                # N3a; candidate-list + deep-merge; supplied synth
|  +- hedge_spec_resolver.py             # N3b; STUB - always loads _default.json (Iter-1)
|  +- profile_spec_validator.py          # N3c; JSON Schema + cross-file checks
|  +- provenance.py                      # N6a (Iter-5 FULL I7 invariant; raises on miss)
|  +- draps_client.py                    # DRAPS HTTP; Iter-5 surfaces SOFR+fixed rates
|  +- deterministic_agents.py            # N3 input validator, N4 simulation, etc.
|  +- components/                        # base_sofr.py, tariff.py, sovereign.py, wc.py
|  +- draps-backend/                     # DRAPS V1 server (npm run server, port 4000)
|  +- tests/
|     +- test_api_supplied.py            # Iter-3 (12)
|     +- test_byte_equality_v1.py        # THE LOCK (6) - live DRAPS+ACTUS
|     +- test_composer_derived.py        # Iter-4 (22, parametrised over IN+VN)
|     +- test_composer_supplied.py       # Iter-3 (25)
|     +- test_draps_client_extract.py    # Iter-5 (31; SOFR+rate extractors)
|     +- test_knot.py                    # V1 carried forward
|     +- test_no_silent_default.py       # Iter-4 (7)
|     +- test_profile_resolver_layering.py    # Iter-2 (14)
|     +- test_profile_resolver_supplied.py    # Iter-3 (16)
|     +- test_profile_spec_validator.py       # Iter-2 (14)
|     +- test_provenance_invariant.py    # Iter-5 (50; I7 enforcement)
|     +- test_provenance_supplied.py     # Iter-3 (18; rewritten for Iter-5 raise contract)
|     +- test_simulation_supplied.py     # Iter-3 (9)
|     +- test_wings.py                   # V1 carried forward
+- config/
|  +- hedge-specs/
|  |  +- _default.json
|  |  +- supplied-rates-example.json     # Iter-3
|  +- risk-factor-profiles/
|  |  +- export-import/
|  |     +- _base.json
|  |     +- india-us.json                # corridor layer (IN)
|  |     +- india-us-textiles.json       # commodity leaf (IN-tex; byte-equality anchor)
|  |     +- vietnam-us.json              # corridor layer (VN) - Iter-4
|  |     +- vietnam-us-textiles.json     # commodity leaf (VN-tex) - Iter-4
|  +- risk-factor-components/            # 4 component spec JSONs
|  +- gtap-references/
|     +- armington-elasticities.json     # Iter-4 (first entry: tex=3.8)
+- schemas/                              # 5 JSON Schemas
+- DESIGN/DESIGN-V1/                     # AUTHORITATIVE design docs (see §3)
+- scripts/verify_schemas.py             # PAIRS check (12/12 as of Iter-5; no schema changes this iteration)
+- actus-risk-service-extension1/
   +- actus-docker-networks/
      +- quickstart-docker-actus-rf20-local.yml   # ACTUS docker compose
```

---

## 3. Authoritative documents (read these, not memory)

| Topic | File | Key sections |
|---|---|---|
| Iteration roadmap, status, test inventory | `DESIGN/DESIGN-V1/design-v1-iteration-plan.md` | §1 (iterations 1-12), §4 (test carryover), §5 (status tracking) |
| Node graph, edges, invariants | `DESIGN/DESIGN-V1/design-v1-detailed-design.md` | §1 (textual graph), §6 (DRAPS dispatch options) |
| JSON layering rules, schema contracts | `DESIGN/DESIGN-V1/design-v1-config-architecture.md` | §4 (deep_merge_in_order), §6 (validator cross-file checks) |
| Migration plan (week-by-week, not slice-by-slice) | `DESIGN/DESIGN-V1/design-v1-migration-plan.md` | §2 (V1 files copied), §8 (out-of-scope for V2) |
| Component formulas | `DESIGN/DESIGN-V1/design-v1-risk-factor-catalog.md` | all |

When these conflict with this PROJECT_CONTEXT.md, the design docs win and this file is wrong and needs updating.

---

## 4. Service runtimes

| Service | How to start | Port | Notes |
|---|---|---|---|
| DRAPS backend (V1) | `cd backend/draps-backend && npm run server` | 4000 | required for derived-mode end-to-end (and byte-equality test) |
| ACTUS risk service | `docker compose -f actus-risk-service-extension1/actus-docker-networks/quickstart-docker-actus-rf20-local.yml up` | 8082 | called by DRAPS |
| ACTUS server | (same compose file) | 8083 | upstream of riskservice |
| V2 backend | `cd backend && uvicorn api:app --reload` | (default) | the agent under test |

---

## 5. Iteration status

### Iteration 1 — Byte-Equality Replay ✅ SHIPPED
The architectural lock. V2 reproduces V1 for India-US textiles byte-for-byte. `test_byte_equality_v1.py` (6/6) is the gate that must stay green on every later iteration. `events_digest_sha256 = e5d26f1b8a53dbc260b9e8145a8a15209d8d78d00c522dd90c242bfc2894318a`.

### Iteration 2 — Real Profile Resolver ✅ SHIPPED (V2 NUMBERS LOCKED)
Real candidate-list + `deep_merge_in_order` resolver replaced the Iter-1 stub. `_base.json` + `india-us.json` + `india-us-textiles.json` now compose via deep merge and still produce identical numbers. Five JSON schemas authored. N3c validator runs JSON Schema + cross-file checks. **The 6 byte-equality assertions in `test_byte_equality_v1.py` are the lock. They MUST stay green.**

### Iteration 3 — Supplied Mode (Problem A) ✅ SHIPPED
Caller can pass their own SOFR path and fixed rates via `RunRequest.supplied`. Five deliverables, all green.

**Deliverable list (in shipped order):**

1. `config/hedge-specs/supplied-rates-example.json` (+ `scripts/verify_schemas.py` PAIRS entry)
2. `backend/composer.py` — `mode='supplied' + dispatch='draps_v1'` branch; `backend/graph.py` adds `supplied: dict | None` to `HedgeAdvisorState`
3. `backend/tests/test_composer_supplied.py` (25 cases)
4. **API + Resolver + Simulation honest-deferral, three sub-steps:**
   - 4a. `backend/api.py` — Supplied pydantic models, `RunRequest.supplied`; `tests/test_api_supplied.py` (12 tests)
   - 4b. `backend/profile_resolver.py` — `_synthesize_caller_supplied_profile()` helper; branch at top of `profile_resolver_node` synthesises `{profile_id:"caller_supplied", version:"1.0.0", mode:"supplied", dispatch:"draps_v1", hedge_spec_id:"supplied-rates-example", supplied:{...}}` and skips disk-based candidate scan when `state.get('supplied') is not None`. `profile_resolution_path = ["<synthesized: caller_supplied>"]`. `tests/test_profile_resolver_supplied.py` (16 tests)
   - 4c. `backend/deterministic_agents.py` `simulation_node` — D3 honest-deferral guard AFTER the `validated_inputs` wiring-bug check: raises `NotImplementedError` naming the DRAPS bridge + both viable follow-up paths when `state.get('supplied') is not None`. `tests/test_simulation_supplied.py` (9 tests)
5. `backend/provenance.py` — NEW module (N6a minimal Iter-3 version). Walks `knot_payload['supplied']` and emits stamps `{field, value, source_type='caller_supplied', request_timestamp}`. Derived-mode = no-op pass-through. **NEVER RAISES.** Exposes `SOURCE_TYPE_CALLER_SUPPLIED` at module scope. `backend/graph.py` wires N6a per `design-v1-detailed-design.md §1` e14/e15: `disclosure -> provenance -> memory`. Adds `provenance_report: dict | None` to `HedgeAdvisorState`. `tests/test_provenance_supplied.py` (18 tests)

**Key decisions made in Iter-3 (preserve forward):**

- **State-level vs profile-level `supplied` key naming.** State-level `supplied` uses short keys (`swap_now_fixed`, `swap_later_fixed`). Profile-level `supplied` (inside the synthesised profile object) uses `_rate`-suffixed keys (`swap_now_fixed_rate`, `swap_later_fixed_rate`) because N3c's `_check_mode_invariants` requires the `_rate` suffix for `mode='supplied'`. **This is an existing codebase inconsistency.** The synthesizer bridges the two; neither side's keys were changed. Composer reads `state['supplied']` verbatim (short names); profile-level `supplied` exists only to satisfy N3c's contract.
- **N6a placement = e14/e15, between Disclosure and Memory.** `design-v1-detailed-design.md §1` is authoritative.
- **D3 honest-deferral fires AFTER the `validated_inputs` wiring-bug `RuntimeError`** in `simulation_node`. Structural errors win over known-deferred boundaries by design.

### Iteration 4 — New Corridor / Commodity (Problem B, narrow) ✅ SHIPPED (2026-05-27)
Proved "any corridor, any commodity" architecturally: adding Vietnam-US-textiles required ZERO Python changes. Three config files + two test files; existing resolver, validator, and composer handled the new corridor identically to India-US-textiles. Byte-equality lock still green.

**Deliverable list:**

1. `config/gtap-references/armington-elasticities.json` (NEW folder + first entry `tex` at Armington=3.8 per GTAP 11, Corong et al. 2017).
2. `config/risk-factor-profiles/export-import/vietnam-us.json` — corridor layer. FED_PATH identical to india-us.json (US-side is corridor-independent). Sovereign 100bps base / 140bps peak anchored on S&P BB+ Local Currency LT affirmed for Vietnam June 28, 2025 (cbonds news 3471799, Reuters/HL Sept 2025).
3. `config/risk-factor-profiles/export-import/vietnam-us-textiles.json` — commodity leaf. Tariff/calibration/WC values held IDENTICAL to india-us-textiles by design choice; sovereign carries the BB+ widening.
4. `backend/tests/test_composer_derived.py` (22 cases, parametrised over `india-us-textiles` + `vietnam-us-textiles`). Frozen `EXPECTED_MERGE` fixture in the file is the "known-good fixture" per plan §"ITERATION 4" acceptance.
5. `backend/tests/test_no_silent_default.py` (7 cases). Sentinel for the §0 invariant "no silent fallbacks": unknown corridor returns errors; known corridor + unknown commodity does not synthesize a textile leaf; composer's `dispatch.get(..., "v2_direct")` default routes to NotImplementedError not silent draps_v1 fallback; validator rejects mode/contents contradictions.
6. `scripts/verify_schemas.py` PAIRS extended to 12/12 (added gtap-references row + the two Vietnam profiles).

**Key Iter-4 decisions (preserve forward):**

- **Identical-tariff design choice.** vietnam-us-textiles holds tariff inputs identical to india-us-textiles so the ONLY visible corridor-level differentiator is the sovereign spread. This is the cleanest architectural demo. Real Vietnam-specific tariff sourcing (e.g. the S&P-quoted 20%/46% 2025 US-on-Vietnam figures) is deferred to Iter-9 when live tariff binding actually consumes the values; until then they would be advisory anyway because `dispatch=draps_v1` keeps derivation in DRAPS.
- **Sovereign calibration methodology.** VN BB+ uses 2x the V1 India-BBB anchor (50/70bps -> 100/140bps) reflecting the BB+ vs BBB ratings-ladder gap and the speculative-grade boundary crossing. Methodology placeholder pending Iter-9 live CDS binding.
- **Test files were pre-staged.** `test_composer_derived.py` and `test_no_silent_default.py` were already on disk at the start of Iter-4 (same mechanism that pre-staged the `verify_schemas.py` PAIRS entries). For future iterations: list `backend/tests/` BEFORE authoring new tests; if a file is already there, read it and treat its expected values as canonical (they constrain the config files you'll write).

**Test command (full project regression, from `backend/` with venv active):**
```
pytest tests/test_api_supplied.py tests/test_byte_equality_v1.py tests/test_composer_derived.py tests/test_composer_supplied.py tests/test_no_silent_default.py tests/test_profile_resolver_layering.py tests/test_profile_resolver_supplied.py tests/test_profile_spec_validator.py tests/test_provenance_supplied.py tests/test_simulation_supplied.py -v
```
**Expected: 143 PASSED.** (Iter-3 regression 114 + Iter-4 new tests 29 = 143.) Byte-equality 6/6 still green = the lock holds.

Also run `python ../scripts/verify_schemas.py` -> expect **12/12 passed**.

---

### Iteration 5 — Full Provenance Agent (I7) ✅ SHIPPED (2026-05-27)
Replaced the Iter-3 minimal "never raises" provenance with the full I7 invariant per `design-v1-detailed-design.md §1` (structural lines): every numeric input to N4 traces to one of `{config_file, api, caller_supplied}` with `source_ref` + `checksum_or_ts`. A run with missing source attribution raises `ProvenanceInvariantError` and the LangGraph run fails honestly (no silent pass).

**Deliverable list:**

1. `backend/draps_client.py` extended: `_extract_sofr_path_from_env` and `_extract_fixed_rate_from_payload` helpers surface DRAPS's SOFR path and the two SWAP fixed-leg rates onto `simulation_result`. Earlier iterations dropped these on the floor (only A/B/C totals + events were carried through). Path-0 happy path populates real values; fallback paths 1/2/3 set them to `None` so N6a raises per I7 if a shape-drift path ever activates.
2. `backend/tests/test_draps_client_extract.py` (NEW; 31 tests): pins the extractor contract offline. The byte-equality test still validates the same parsing live; this file covers the same surface without requiring DRAPS+ACTUS.
3. `backend/provenance.py` REWRITTEN: full I7 enforcement. `SOURCE_TYPE_CONFIG_FILE`, `SOURCE_TYPE_API` (reserved for Iter-8+), and `SOURCE_TYPE_CALLER_SUPPLIED` are the legal source-type set. `ProvenanceInvariantError(RuntimeError)` is the named exception. Derived-mode stamps every SOFR point + 2 fixed rates as `config_file` (leaf profile + hedge spec); supplied-mode stamps the supplied block as `caller_supplied`; loan fields are `caller_supplied` in BOTH modes (per the C2 design call — see Key decisions below). Report carries `resolved_profile_files` (full merge chain with sha256s) and `resolved_hedge_spec_file` in derived mode.
4. `backend/tests/test_provenance_invariant.py` (NEW; 50 tests): pins the I7 contract end-to-end. Sections cover stamp shape, source-type taxonomy, derived-mode happy path (per-SOFR-point sha256 attribution), report extras (merge chain), loan-field stamps, supplied-mode happy path, hedge-spec path recovery, 22 raise-on-missing tests, composer integration, audit log.
5. `backend/tests/test_provenance_supplied.py` REWRITTEN IN PLACE: still 18 tests. Per-test categorisation per the Iter-5 plan: 7 supplied-mode tests UPDATED (count 5→9 with loan fields; stamp shape `request_timestamp` → `checksum_or_ts`+`source_ref`); 9 boundary tests REPLACED (Iter-3 "never raises" → Iter-5 "raises per I7") — same boundaries guarded, assertion direction flipped; 1 composer-integration test UPDATED for count; 1 graph-build smoke test unchanged. Shared fixtures restructured to place `validated_inputs` at top of state.

**Key Iter-5 design decisions (preserve forward):**

- **Strategy A1: per-SOFR-point attribution via `draps_client` extension.** For dispatch=draps_v1 (Iter-5's only shipped derived path), DRAPS computes SOFR points internally. The honest attribution is per SOFR point with `source_type=config_file`, `source_ref` = profile leaf path, `checksum_or_ts` = sha256 of leaf file. The alternative considered (A4: stamp the sources that DRIVE SOFR, not per-output-point) was rejected because the iteration-plan §1 acceptance says "enumerates every numeric in sofr_path". When `dispatch=v2_direct` ships in a later iteration, per-(point, component) attribution will become possible and the derived branch will extend.
- **C2: loan fields use `source_type=caller_supplied` (not a new fourth type).** The iteration-plan §1 ITERATION 5 acceptance enumerates exactly three source types `{config_file, api, caller_supplied}`. Loan fields arrive via the caller's POST body (private_loan_doc + prompt → N1/N2/N3 chain), which qualifies as I7 (c) "caller-supplied input + the message/field where it arrived". Disambiguation from supplied-mode SOFR comes from `source_ref` (`"request.body.private_loan_doc -> validated_inputs.loan.X"` vs `"request.body.supplied.sofr_path[i].value"`), not from a different source_type. C1 (inventing `validated_intake`) was rejected as docs-violation.
- **B1: sha256 computed inside N6a, no `profile_resolver.py` changes.** Iter-5 is provenance-only; resolver stays untouched. N6a reads `state.profile_resolution_path` (paths) and hashes each layer at runtime. File I/O cost is negligible (3 small JSON files per derived run).
- **F1: no hedge-spec-path fallback from `state.hedge_spec_id`.** The Iter-1 N3b stub always emits an `audit_log` entry with the `output.source` relative path. That's the SOLE recovery channel. `state.hedge_spec_id` is the spec_id field INSIDE the JSON (e.g. "default-3-scenario"), not the filename (`_default.json`) — mapping is not 1:1. Real runs always traverse N3b so the audit entry always exists; tests that construct state directly must include it too.
- **Stamp shape locked: `{field, value, source_type, source_ref, checksum_or_ts}`.** Per `design-v1-detailed-design.md §2` (HedgeAdvisorStateV2 `knot_payload.provenance`). Iter-3's stamp shape used `request_timestamp`; Iter-5 renamed it to `checksum_or_ts` so config_file stamps carry sha256 and caller_supplied stamps carry ISO 8601 UTC in the same field.

**Test command (full project regression, from `backend/` with venv active):**
```
pytest tests/test_api_supplied.py tests/test_byte_equality_v1.py tests/test_composer_derived.py tests/test_composer_supplied.py tests/test_draps_client_extract.py tests/test_no_silent_default.py tests/test_profile_resolver_layering.py tests/test_profile_resolver_supplied.py tests/test_profile_spec_validator.py tests/test_provenance_invariant.py tests/test_provenance_supplied.py tests/test_simulation_supplied.py -v
```
**Expected: 224 PASSED.** (Iter-4 regression 143 + Iter-5 new tests 31 + 50 = 224. `test_provenance_supplied.py` stayed at 18 tests after the Iter-5 rewrite.) Byte-equality 6/6 still green = the lock holds.

Also run `python ../scripts/verify_schemas.py` -> expect **12/12 passed** (no schema changes this iteration).

---

## 6. Open items (preserve across iterations)

1. **TOP PRIORITY when end-to-end supplied mode is needed: DRAPS bridge for supplied SOFR path.** D3 honest-deferral currently raises `NotImplementedError` in `simulation_node` when `state['supplied']` is set. Two viable paths (encoded in the exception message):
   - **(a)** modify DRAPS-side Postman JS in `DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json` to honour a `supplied_sofr_path` in `configData`, OR
   - **(b)** skip DRAPS in supplied mode and call ACTUS directly from V2.
2. **`hedge_spec_resolver.py` still an Iter-1 stub** — always loads `_default.json` regardless of `profile.hedge_spec_id`. The synthesised supplied profile sets `hedge_spec_id="supplied-rates-example"` but the resolver doesn't honour it yet. **Not breaking** — composer routes on `(mode, dispatch)`, not on `spec_id`.
3. **Country-code normalisation gap (carried from Iter-2).** `market_context_node` asks the LLM for ISO codes, but live-graph behaviour is unverified. Fix in N3 validator.
4. **`config/corridor-references/` folder still not on disk.** Schemas exist for sovereign-ratings.json + policy-rate-paths.json; the directory and files don't. (`config/gtap-references/` was created in Iter-4.) Probably picked up in Iter-9 alongside live data binding.
5. **DRAPS-side tariff escalation discrepancy.** `draps_client.py:_build_config_data` sends `tariff_current=tariff_peak` (flat), but `india-us-textiles.json` and `vietnam-us-textiles.json` both declare escalation (0.50 -> 0.60). Advisory until `dispatch=v2_direct`, then needs reconciliation.

---

## 7. Next iteration: Iteration 6 — Domestic Services (Problem C, slice 1)

**Goal (from `design-v1-iteration-plan.md §1`, ITERATION 6):** smallest possible domestic-mode end-to-end. Pick services first because it needs the fewest new components.

**Build:**
- Two new components: `backend/components/demand_volatility.py`, `backend/components/payment_cycle.py`. (Reuse the existing `base_sofr.py` and `wc.py`.)
- Author `config/risk-factor-profiles/domestic/us-services.json` and `_base_domestic.json`.
- All component sources resolve to **snapshot files** under `backend/tests/fixtures/snapshots/` — no live API calls in this iteration (live FRED/Census/BLS bindings are Iter-8/9).
- Extend N1 Intake to extract `business_identity.mode = "domestic_services"`.
- Extend N2 Market-Context to resolve NAICS sector instead of GTAP code when mode is domestic.
- Add `backend/tests/test_composer_derived_domestic.py`.

**Acceptance:**
- Synthetic US SaaS loan → recommendation runs end-to-end.
- Recommendation rationale (from N5) does **not** mention tariff, sovereign, or commodity.
- Provenance report shows `source_type: "config_file"` for component snapshots (with `source_ref` pointing to the snapshot file path); the snapshot date appears in the snapshot file metadata.
- Byte-equality and all previous tests green (224 + Iter-6 additions).

**Pre-iteration check:**
- **LIST `backend/tests/` BEFORE authoring new test files** (Iter-4 lesson, re-confirmed in Iter-5). Files may be pre-staged. If a test file is already on disk, read it and treat its expected values as canonical — they constrain the config files you'll write.
- **Profile resolver mode handling.** `profile_resolver.py:_derive_business_identity` currently hardcodes `mode="export_import"`. Iter-6 needs N2 Market-Context to write a real `business_identity.mode` and the resolver to honor it. This is a real change to the Iter-2/3 resolver (not just additive).
- **N6a derived branch is dispatch=draps_v1-shaped.** For domestic profiles, dispatch will be `v2_direct` (V2 computes SOFR itself per-component). N6a's `_stamp_derived_sofr_and_rates` currently reads `simulation_result.sofr_path` from DRAPS output; Iter-6 (or Iter-4's deferred v2_direct) needs an extended attribution model where each SOFR point traces to the specific component(s) that contributed bps to it. The current per-point-to-leaf-file attribution is a stopgap that works for draps_v1 only.

**START HERE in the new chat:**
  1. Read PROJECT_CONTEXT.md at the project root.
  2. Confirm 224/224 still green by running the full regression command in the §8 health-check.
  3. Read `backend/profile_resolver.py` and `backend/deterministic_agents.py:simulation_node` in full — understand current mode handling and the dispatch=draps_v1 path.
  4. Outline the Iter-6 work as a per-deliverable plan; stop for confirmation before authoring code.

---

## 8. How to verify the project is healthy

From `backend/` with the venv active, three commands:

```
python ../scripts/verify_schemas.py
pytest tests/test_draps_client_extract.py tests/test_provenance_invariant.py -v
pytest tests/test_api_supplied.py tests/test_byte_equality_v1.py tests/test_composer_derived.py tests/test_composer_supplied.py tests/test_draps_client_extract.py tests/test_no_silent_default.py tests/test_profile_resolver_layering.py tests/test_profile_resolver_supplied.py tests/test_profile_spec_validator.py tests/test_provenance_invariant.py tests/test_provenance_supplied.py tests/test_simulation_supplied.py -v
```

Expect, in order: **12/12 schema rows OK**, **81 Iter-5 tests passed** (31 draps extract + 50 provenance invariant), **224 tests passed** with the byte-equality 6/6 lock green. If anything fails, **STOP** and investigate before starting new work — the byte-equality lock and all Iter-3+Iter-4+Iter-5 contracts are load-bearing.

`test_byte_equality_v1.py` requires DRAPS (port 4000) and ACTUS (ports 8082/8083) running per §4. The other 11 test files are pure Python — safe in any CI environment.
