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
|  +- components/                        # base_sofr, tariff, sovereign, wc, demand_volatility, payment_cycle (Iter-6), inventory_carrying (Iter-7)
|  +- data_sources/                       # Iter-8: fred_client.py, snapshot_cache.py, api_binding.py (live FRED/SOFR bind)
|  +- draps-backend/                     # DRAPS V1 server (npm run server, port 4000)
|  +- tests/
|     +- test_api_supplied.py            # Iter-3 (12)
|     +- test_byte_equality_v1.py        # THE LOCK (6) - live DRAPS+ACTUS
|     +- test_composer_derived.py        # Iter-4 (22, parametrised over IN+VN)
|     +- test_composer_supplied.py       # Iter-3 (25)
|     +- test_composer_derived_domestic.py    # Iter-6 (8) + Iter-7 (9) - same file, banner-sectioned
|     +- test_honest_failure.py          # Iter-8 (9; CI-safe, FRED HTTP monkeypatched)
|     +- test_draps_client_extract.py    # Iter-5 (31; SOFR+rate extractors)
|     +- test_knot.py                    # V1 carried forward
|     +- test_no_silent_default.py       # Iter-4 (7)
|     +- test_profile_resolver_layering.py    # Iter-2 (14)
|     +- test_profile_resolver_supplied.py    # Iter-3 (16)
|     +- test_profile_spec_validator.py       # Iter-2 (14)
|     +- test_provenance_invariant.py    # Iter-5 (50; I7 enforcement)
|     +- test_provenance_supplied.py     # Iter-3 (18; rewritten for Iter-5 raise contract)
|     +- test_simulation_supplied.py     # Iter-3 (9)
|     +- test_simulation_v2_direct.py    # Iter-6a (10; ACTUS monkeypatched)
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
|  |  +- domestic/                       # Iter-6/7/8 derived_domestic profiles
|  |     +- _base_domestic.json           # base layer (Iter-6)
|  |     +- us-services.json              # us-services-v1 (Iter-6)
|  |     +- us-ecommerce.json             # us-ecommerce-v1 (Iter-7)
|  |     +- us-services-live.json         # us-services-live-v1 (Iter-8; live FRED bind on base_sofr.initial)
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

### Iteration 6a — v2_direct Dispatch (foundation for domestic) ✅ SHIPPED (2026-05-28)
First V2-internal SOFR derivation path. `simulation_node` gains a `v2_direct` branch + `actus_client.run_v2_direct`: when the composer ran `dispatch='v2_direct'` (mode `derived`/`derived_domestic`) and stamped `knot_payload['v2_direct']`, the node derives A/B/C by building scenario batches and POSTing each to ACTUS `/eventsBatch` — short-circuiting BEFORE the draps_v1 path (DRAPS not called). Aggregation replicates `DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json`: A = abs ΣIP(loan); B = abs IP(LOAN-FLOAT-B) − signed IP(SWAP-NOW-B); C = abs IP(LOAN-FLOAT-C) − signed IP(SWAP-LATER-C). Non-IP events (IED/MD/RR) excluded. Loan PAM `nominalInterestRate = _to_fixed4(sofr0 + loan_spread)`; scenario-C FLOAT leg picks SOFR @ swap_start (loan_start + 3mo), NOT `sofr_path[0]`. The `validated_inputs` wiring guard still fires first.
**Deliverable:** `backend/tests/test_simulation_v2_direct.py` (10 tests, CI-safe, ACTUS monkeypatched). Resolves the Iter-4/5 "v2_direct deferred" open item. **Test count: 10** (verified by full read; none parametrised).

---

### Iteration 6 — Domestic Services (Problem C, slice 1) ✅ SHIPPED (2026-05-28)
Smallest domestic-mode end-to-end (services). **Resolver domestic arm:** `_classify` / `_scan_candidates` domestic branch; `_derive_business_identity` now reads `business_mode + industry` only (`naics_sector` / `rate_curve_index` inert). Resolves `us-services.json` (sector) over `_base_domestic.json` (base) → `profile_id='us-services-v1'`, `mode='derived_domestic'`, `dispatch='v2_direct'`, `applies_to={mode:domestic, industry:services}`. **Composer Branch 3** (`derived_domestic` + `v2_direct`): `_build_sofr_path` sums 4 components `[base_sofr, demand_volatility, payment_cycle, wc]` over a 9-point quarterly grid (`TENOR_POINTS=9`, `STEP=3mo` from loan start); `_apply_fixed_rate_rule('discount_from_path')` → `swap_now = round4(sofr@+0 − 100bps)`, `swap_later = round4(sofr@+3 − 70bps)` using `_default.json` discounts. Provenance stamp: `derived_domestic`/`v2_direct`, config_file sourcing, `hedge_spec_id='default-3-scenario'`.
**Config detail (verified):** `us-services.json` carries `base_sofr` at the V1 FED_PATH anchor (initial 4.50% / peak 5.50% / final 4.75%), `demand_volatility` `pmi_current=48.0` (vs `pmi_neutral=50.0`), `payment_cycle` `dso_observed=58` vs `dso_median=35`, `wc` 30→50 bps; `loan_spread_default=0.025`; `tenor_grid` quarterly / 24-month / anchored at `loan_start_date`. **All `source.type='config_file'`** (Flag-2 resolution: `LEGAL_SOURCE_TYPES` was NOT extended with a 4th `'snapshot'` type) with `source.ref` → `tests/fixtures/snapshots/us-services-*-2026q1.json`, `snapshot_date='2026-01-31'`. `_base_domestic.json` holds the shared 4-component skeleton + 12/3/9 `stress_timing` + 250bps default spread.
**Deliverables:** `components/demand_volatility.py` + `payment_cycle.py` (NEW; closed forms, docstrings "signed off by user"); `config/risk-factor-profiles/domestic/us-services.json` + `_base_domestic.json` (NEW); `backend/tests/test_composer_derived_domestic.py` (NEW, Iter-6 section = 8 tests).
**KEY DECISION:** Iter-6 tests assert STRUCTURE / relationships, NOT frozen absolute 9-point values — `us-services.json` inputs are ILLUSTRATIVE pending live-source binding. **DOC-DEBT (carried, plan doc only):** the plan §1 Iter-6 acceptance literal text reads `source_type:'snapshot'`; reconciled to `config_file` per Flag-2 — the fix to the *plan doc* text is "Iter-6 deliverable 11" and is still pending (plan doc not edited this session). **Test count (Iter-6 section): 8** (verified by full read).

---

### Iteration 7 — Domestic Ecommerce (Problem C, slice 2) ✅ SHIPPED (2026-05-29)
Consumer-facing domestic case; adds inventory-cycle dynamics; still snapshot/illustrative-input mode. `us-ecommerce.json` (`'us-ecommerce-v1'`) resolves through the SAME domestic arm + Branch 3, selecting the catalog 'Ecommerce' column `[base_sofr, demand_volatility, payment_cycle, wc, inventory_carrying]`. `inventory_carrying` is **overlay-only** (appended via deep-merge); `payment_cycle` is **RETAINED** (not substituted); NO `_base` change, NO resolver change, NO `_base_ecommerce.json` (a second `applies_to={mode:domestic}` base file would collide on the base layer). New component `inventory_carrying.py` (`formula_id inventory_carrying_dso_dpo`): `abs(ISR − historic_mean)` (gluts AND stockouts both widen WC), `peak_bps = baseline + dev*sensitivity*dio_sensitivity`, shared trapezoid.
**Config detail (verified):** `inventory_carrying` inputs `isr_observed=1.62`, `isr_historic_mean=1.45`, `sensitivity_bps_per_ratio_point=200`, `dio_sensitivity=1.0` (placeholder), `baseline_bps=3.0`; `demand_volatility` `pmi_current=47.0`; `payment_cycle` `dso_observed=45`; `wc` peak bumped to 60bps (vs 50 for services). `_base_domestic.json`'s `_notes` was reconciled (it no longer claims ecommerce "substitutes inventory_carrying for payment_cycle"; the matrix keeps both).
**Deliverables:** `components/inventory_carrying.py` (NEW); `config/risk-factor-profiles/domestic/us-ecommerce.json` (NEW); `test_composer_derived_domestic.py` EXTENDED (+9 tests: ecommerce resolver/composer/provenance/audit + 3 `inventory_carrying` unit tests locking baseline floor / glut-stockout symmetry / peak formula).
**KEY DECISIONS:** numeric vector still NOT frozen (illustrative inputs); unit tests lock FORM not magnitudes. `inventory_carrying` v1 baseline is **SIGNED OFF** (user-confirmed this session); the fuller CCC form (DIO+DSO−DPO) is deferred without architecture change. The stale "PENDING USER SIGN-OFF" note in the test file is to be corrected to reflect sign-off. **Test count (Iter-7 addition): 9** (verified by full read).

---

### Iteration 8 — Live FRED/SOFR Binding (Option A) ✅ SHIPPED (2026-05-29)
First live external-data bind. `us-services-live.json` (`'us-services-live-v1'`, `applies_to.industry='services-live'`) is a SEPARATE profile (not an in-place edit of `us-services.json`) so the Iter-6/7 offline regression stays deterministic — a treasurer selects `industry='services-live'` for live rates; CI/offline keep `industry='services'`. **HYBRID bind:** `base_sofr.initial` is bound LIVE from FRED `SOFR` latest observation (`source.type='api'`, `provider='FRED'`, `series_id='SOFR'`, `binds='initial'`); `peak`/`final` remain the declared V1 anchor (5.50%/4.75%) pending a Fed dot-plot source. `cache_policy` (`mode='cached_within_days'`, `max_age_days=4`) lives INSIDE `base_sofr.source` (free-form object → no schema change). `demand_volatility`/`payment_cycle`/`wc` are IDENTICAL to `us-services.json` (still config_file; Census/BLS bindings are Iter-9). New package `backend/data_sources/{fred_client,snapshot_cache,api_binding}.py`. `profile_resolver` gained `needs_key` lazy-config decoupling (offline path imports no api component → no config import).
**Deliverable:** `backend/tests/test_honest_failure.py` — all CI-safe (offline path via `needs_key` decoupling; api-path tests monkeypatch `_fred_api_key` via `patch_key` or bypass the node).
**STILL PENDING SIGN-OFF (user, carried):** `us-services-live.json` as a SPLIT vs flipping `us-services.json` in place; `cache_policy max_age_days=4` as the SOFR staleness window. **STILL OWED (user, cannot run from sandbox — no Windows exec, FRED not allow-listed):** live FRED smoke (real `FRED_API_KEY` in `backend/.env`, resolve `industry='services-live'`, confirm `base_sofr.inputs.initial == live SOFR fraction` and `source.binding_result.freshness == "live"`).
**Test count: 9** (verified — full regression run 2026-05-29 confirms 9/9 in `test_honest_failure.py`). **STATUS: shipped 2026-05-29 — full regression 260 PASSED, byte-equality 6/6 green (run live with DRAPS+ACTUS up). Cumulative = Iter-5 base 224 + 6a 10 + Iter-6 8 + Iter-7 9 + Iter-8 9 = 260; no regression — `test_no_silent_default.py`'s 2 rewritten v2_direct composer tests pass, so the 224 base is intact under shipped v2_direct. Schema check now 15/15 (Iter-6/7 added the 3 domestic profiles to verify_schemas PAIRS).**

---

### Iteration 9 - Live FRED ISRATIO bind (inventory_carrying) ✅ SHIPPED (2026-05-30)
Second live external-data bind. SCOPE COLLAPSED during scoping (evidence-based against `design-v1-risk-factor-catalog.md` + `design-v1-free-apis.md` + the profile JSONs): the ONLY Iter-9-bindable component beyond the Iter-8 SOFR bind is `inventory_carrying.isr_observed` -> FRED `ISRATIO`. `us-ecommerce-live.json` (`'us-ecommerce-live-v1'`, `applies_to.industry='ecommerce-live'`) is a SEPARATE profile (same split rationale as `us-services-live.json`): clones `us-ecommerce.json` and flips TWO component sources to `source.type='api'` - `base_sofr.initial` <- FRED `SOFR` (cache `max_age_days=4`, same hybrid bind as Iter-8) and `inventory_carrying.isr_observed` <- FRED `ISRATIO` (cache `max_age_days=45`, monthly series). `demand_volatility`/`payment_cycle`/`wc` stay `config_file`/snapshot. CI/offline keep `industry='ecommerce'`.
**Binding mechanics (verified in code):** `fred_client.fetch_latest_sofr` gained a keyword-only `value_scale` param; `api_binding._BINDABLE` is now `formula_id -> (field, provider, series_id, value_scale)` with `base_sofr_fed_path_linear -> ("initial","FRED","SOFR",0.01)` and `inventory_carrying_dso_dpo -> ("isr_observed","FRED","ISRATIO",1.0)`. ISRATIO is a RATIO, bound AS-IS with `value_scale=1.0` (NOT the 0.01 percent-rate scaling - binding ~0.0145 instead of ~1.45 would be the bug). Provider/series_id are read from `_BINDABLE` keyed by `formula_id`, NOT from `source.provider`; the `provider != "FRED"` guard rejects any future non-FRED entry with an honest "not wired" error (Census/BLS deferred).
**SCOPE DECISIONS (locked, evidence-grounded):** (1) `census_client.py` DEFERRED - Census MRTS query/field shape unverifiable from sandbox (api.census.gov unreachable). (2) `bls_client.py` DEFERRED - no Iter-9 component consumes a BLS series. (3) `demand_volatility.pmi_current` STAYS SNAPSHOT - no free PMI REST API. (4) `payment_cycle.dso_observed` STAYS SNAPSHOT - Atradius/Intuit/Fed SBCS/JPMC are free REPORTS, not APIs. (5) `wc_trapezoidal` OUT - inputs are output bps, no market observable. (6) `config/corridor-references/` folder NOT created (carried, see open items).
**Deliverables:** `backend/data_sources/fred_client.py` + `api_binding.py` EDITED (value_scale + ISRATIO `_BINDABLE` entry); `config/risk-factor-profiles/domestic/us-ecommerce-live.json` (NEW); `backend/tests/fixtures/snapshots/us-ecommerce-{pmi,dso,wc,isr}-2026q1.json` (NEW - referenced by us-ecommerce.json since Iter-7 but never on disk); `backend/tests/test_honest_failure.py` EXTENDED (+5 Iter-9 tests, NO new file); `scripts/verify_schemas.py` PAIRS +2 (`us-ecommerce-live.json` AND `us-services-live.json` - the latter a carried Iter-8 gap, never added in Iter-8).
**STILL PENDING SIGN-OFF / OWED (user, carried):** (a) wc Iter-9 in/out conflict - `us-services-live.json` _notes and `us-ecommerce.json` wc citation both label the ISRATIO->wc bind as Iter-9, contradicting the locked decision to keep wc OUT; built OUT, user to confirm/override. (b) `inventory_carrying` cache `max_age_days=45` sign-off (monthly ISRATIO; SOFR's 4 would reject every fallback). (c) SMOKE: `series_id="ISRATIO"` magnitude - FRED's literal ISRATIO is Total-Business inv/sales (~1.37); docs describe Retailers' ratio (~1.45); verify on real-key smoke, swap series_id if retailers'-specific intended (NOT guessed here). (d) carried Iter-8 live FRED/SOFR smoke + the Iter-8 split/cache sign-offs still owed.
**Test count (Iter-9 addition to `test_honest_failure.py`): +5** (`test_isr_live_success_binds_as_ratio_value_scale_one` [value_scale regression guard], `test_isr_outage_no_cache_gives_up`, `test_isr_outage_overage_cache_gives_up`, `test_isr_outage_within_45d_uses_stale_and_stamps_it`, `test_non_fred_provider_not_wired`). `test_honest_failure.py` now 14. **STATUS: shipped 2026-05-30 - full regression 265 PASSED, byte-equality 6/6 green (run live with DRAPS+ACTUS up, Windows-side). Cumulative = Iter-8 260 + Iter-9 5 = 265. Schema check now 17/17 (added both live profiles to verify_schemas PAIRS). Live external smoke (real FRED key against api.stlouisfed.org) still owed - the regression monkeypatches the HTTP layer, exactly as Iter-8.**

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

## 7. Next iteration: Iteration 10 — scope per `design-v1-iteration-plan.md §1 → ITERATION 10` (NOT read this session)

> **Iterations 6, 6a, 7, 8, 9 are SHIPPED — see §5.** Iteration 9 bound `inventory_carrying.isr_observed` → FRED ISRATIO (and carried the Iter-8 SOFR hybrid bind into `us-ecommerce-live.json`). The broader "live Census/BLS bindings" originally sketched in this section did NOT ship — they were DEFERRED on evidence (no free PMI/DSO REST APIs; Census MRTS query shape unverifiable from sandbox; no Iter-9 BLS consumer). See the §5 Iteration 9 block (SCOPE DECISIONS) for the full reasoning. **Authoritative Iter-10 plan = `design-v1-iteration-plan.md §1 → ITERATION 10`; read it before starting. NOT read this session.**

**Deferred from Iter-9 (candidates for a later iteration; NOT yet scoped against plan §1 ITERATION 10):**
- `demand_volatility.pmi_current` live bind — needs a reformulation onto a free signal (e.g. FRED ECOMPCTSA / Census E-commerce Retail); changes the component input + formula.
- `payment_cycle.dso_observed` live bind — sources are free REPORTS (Atradius / Intuit / Fed SBCS / JPMC), not REST APIs; needs a report-ingest path, not an api client.
- `census_client.py` / `bls_client.py` — build only when a consumer AND a verified query shape both exist.
- `config/corridor-references/` folder still not on disk (§6 item 4).
- The Iter-9 user sign-offs / smoke listed in the §5 Iteration 9 block: wc in/out conflict, `inventory_carrying` `max_age_days=45`, the `series_id="ISRATIO"` magnitude smoke, and the carried Iter-8 SOFR smoke + split/cache sign-offs.

**Pre-iteration check (standing lesson, Iter-4/5/6):**
- **LIST `backend/tests/` BEFORE authoring new test files.** Files may be pre-staged; if present, read them and treat their expected values as canonical.

**START HERE in a new chat:**
  1. Read PROJECT_CONTEXT.md at the project root.
  2. Run the §8 health-check; confirm 265 PASSED + byte-equality 6/6 green + schema 17/17.
  3. Read `design-v1-iteration-plan.md §1` (ITERATION 10) for authoritative scope.
  4. Outline Iter-10 per-deliverable; stop for confirmation before authoring code.

---

## 8. How to verify the project is healthy

From `backend/` with the venv active, three commands:

```
python ../scripts/verify_schemas.py
pytest tests/test_draps_client_extract.py tests/test_provenance_invariant.py -v
pytest tests/test_api_supplied.py tests/test_byte_equality_v1.py tests/test_composer_derived.py tests/test_composer_derived_domestic.py tests/test_composer_supplied.py tests/test_draps_client_extract.py tests/test_honest_failure.py tests/test_no_silent_default.py tests/test_profile_resolver_layering.py tests/test_profile_resolver_supplied.py tests/test_profile_spec_validator.py tests/test_provenance_invariant.py tests/test_provenance_supplied.py tests/test_simulation_supplied.py tests/test_simulation_v2_direct.py -v
```

Expect, in order: **17/17 schema rows OK**, **81 Iter-5 tests passed** (31 draps extract + 50 provenance invariant), and the full regression **265 PASSED** (verified 2026-05-30, Windows-side, DRAPS+ACTUS up) with the byte-equality 6/6 lock green. New-tests-since-Iter-5 (verified per-file, none parametrised): +10 (6a `test_simulation_v2_direct`) +8 (Iter-6 section of `test_composer_derived_domestic`) +9 (Iter-7 section, same file) +9 (Iter-8 `test_honest_failure`) +5 (Iter-9 ISRATIO section of `test_honest_failure`) = +41. **The 2026-05-30 run confirms 224 + 41 = 265 with no regression:** `test_no_silent_default.py` kept its 7-count and its 2 rewritten 6a composer tests (`test_composer_default_dispatch_v2_direct_raises_not_silent_fallback`, `test_composer_explicit_v2_direct_raises_not_silent_fallback`) both pass, so the Iter-5 base of 224 is intact under the shipped `v2_direct` branch. If a future run shows anything failing, **STOP** and investigate before starting new work — the byte-equality lock and all Iter-3→Iter-8 contracts are load-bearing.

`test_byte_equality_v1.py` requires DRAPS (port 4000) and ACTUS (ports 8082/8083) running per §4. The other 14 test files in the regression set are pure Python / monkeypatched — safe in any CI environment. This INCLUDES `test_honest_failure.py` (FRED HTTP monkeypatched) and `test_simulation_v2_direct.py` (ACTUS monkeypatched); note this insulates the TESTS, not production — a real api-mode resolution (`industry='services-live'`) still needs `FRED_API_KEY` from config.
