# hedgeAdvisor2 — design-v1-iteration-plan

> **Iterations, not phases.** The migration plan (`design-v1-migration-plan.md`) groups work by *layer* over multi-week blocks. This plan groups work by *vertical slice* — every iteration produces a working, demoable end-to-end run (prompt → A/B/C → recommendation), starting from the smallest possible one. After each iteration you can demo something real. No iteration is "scaffolding only."

> **Sequencing rule.** Each iteration adds one capability and keeps every prior acceptance test green. The byte-equality regression from Iteration 1 is the gate that runs on every iteration that follows.

---

## 0. The thread that runs through every iteration

Three things are true for every iteration on this list:

1. **The byte-equality test for India-US textiles stays green.** It is the architectural lock. Any iteration that breaks it is rejected.
2. **No silent fallbacks, no hardcoding, no mocks.** Honest failure is preferred to a wrong answer. Per V1 discipline.
3. **The work ends with a passing test the user can re-run.** "Done" means a test runs green, not a file is written.

---

## 1. The iterations

### ITERATION 1 — Byte-Equality Replay (THE GATE)
**STATUS:** shipped 2026-05-27, byte-equality green (6/6 tests pass; events_digest_sha256=`e5d26f1b8a53dbc260b9e8145a8a15209d8d78d00c522dd90c242bfc2894318a`).
**Goal:** prove the new bow-tie can reproduce V1 byte-for-byte. Smallest possible end-to-end V2.

**Build:**
- Capture V1 ground truth (`scripts/capture_v1_baseline.py`) → `backend/tests/fixtures/v1-baseline/india-us-textiles.json` containing the SOFR path, `swap_now_fixed_rate`, `swap_later_fixed_rate`, A_total, B_total, C_total, and the events digest.
- Copy unchanged V1 backend files into `hedgeAdvisor2/backend/` (main, api, config, gemini_client, actus_mentor_client, memory_store, explanation_agent — see migration-plan §2).
- Author one config file: `config/risk-factor-profiles/export-import/india-us-textiles.json` with V1 constants verbatim (per config-architecture §3.1).
- Author one hedge-spec: `config/hedge-specs/_default.json` (V1 swap discounts: 100bps now, 70bps later).
- Author four component spec JSONs + Python ports of the V1 Postman JS:
  `components/base_sofr.py`, `tariff.py`, `sovereign.py`, `wc.py`.
- Write a **stub** Profile-Resolver (N3a) that hardcodes the load of `india-us-textiles.json` — no candidate-list logic yet. Stub Hedge-Spec-Resolver and Validator that just pass through.
- Build a minimal `composer.py` that supports `mode: derived` only.
- Rewire `graph.py`: N3 → N3a-stub → N3b-stub → N3c-stub → N3d → N4.
- Pick DRAPS dispatch path: **Option 3** from detailed-design §6 — keep the V1 `draps_v1` path for this profile. Confirm by reading `generalRisk/Backend/src/routes/simulation.routes.ts` before writing the call.

**Acceptance:**
- `test_byte_equality_v1.py` passes: SOFR path matches V1 fixture to 4 decimal places; A/B/C totals match exactly.
- V1 tests (`test_knot.py`, `test_wings.py`) copied across pass unchanged.

**Demo:** V1 prompt → V2 produces identical numbers to V1, but the trace shows the 4 new nodes executed.

**Why this is iteration 1, not iteration 0:** because it ends with a working, deployable, demoable system. There is no "scaffolding-only" phase.

---

### ITERATION 2 — Real Profile Resolver (kill the hardcoding)
**STATUS:** shipped 2026-05-27, byte-equality green (6/6 tests pass; same `events_digest_sha256=e5d26f1b8a53dbc260b9e8145a8a15209d8d78d00c522dd90c242bfc2894318a` as Iter-1 — numbers reproduced via real merge of `_base → india-us → india-us-textiles` instead of the Iter-1 stub).
**Goal:** replace the Iteration-1 stub with the real candidate-list + merge resolver. Byte-equality must still hold.

**Build:**
- Author `config/risk-factor-profiles/export-import/_base.json` (export-import common defaults) and `india-us.json` (corridor-level, no commodity override).
- Implement `profile_resolver.py` with the candidate-list + `deep_merge_in_order` logic from detailed-design §4.
- Author the 5 JSON schemas in `schemas/` (profile, component, hedge-spec, gtap-armington, sovereign-rating).
- Implement `profile_spec_validator.py` (N3c) running JSON Schema + cross-file checks from config-architecture §6.
- Add `test_profile_resolver_layering.py` and `test_profile_spec_validator.py`.

**Acceptance:**
- Byte-equality test from Iteration 1 still green — same numbers, now produced via real merge of `_base → india-us → india-us-textiles`.
- `profile_resolution_path` in the state lists all three files in order.
- A profile with a bad `formula_id` reference is rejected by N3c and routes to GIVE-UP — no silent acceptance.

**Demo:** ChatPanel trace shows the resolution path. Edit `india-us.json` to override `pass_through`, re-run — number changes; revert and confirm byte-equality restored.

---

### ITERATION 3 — Supplied Mode (Problem A)
**STATUS:** shipped 2026-05-27, byte-equality green (6/6 tests pass; full Iter-3 regression 114/114). Added: `composer.py` supplied dispatch; `api.py` Supplied pydantic models; `profile_resolver.py` `_synthesize_caller_supplied_profile()`; `deterministic_agents.py` simulation_node D3 honest-deferral; `provenance.py` N6a minimal; `supplied-rates-example.json` hedge spec.
**Goal:** caller can pass their own SOFR path + fixed rates and skip the derivation entirely.

**Build:**
- Extend `composer.py` to handle `mode: supplied`.
- Extend `POST /run` body shape: accept either V1 shape OR `{prompt, loan_doc, supplied: {sofr_path, swap_now_fixed, swap_later_fixed}}`.
- Author `config/hedge-specs/supplied-rates-example.json`.
- Implement minimal N6a Provenance Agent that stamps `source_type: "caller_supplied"` for the supplied numbers and records the request timestamp.
- Add `test_composer_supplied.py`.

**Acceptance:**
- Caller supplies a SOFR path of their choice → DRAPS receives exactly that path → A/B/C totals reflect it.
- Byte-equality test green (V1 path untouched).
- Provenance report distinguishes supplied numbers from derived ones.

**Demo:** treasurer flow — paste a SOFR curve into the request, see A/B/C for "their" curve, see the provenance report flag "caller-supplied" on every input.

---

### ITERATION 4 — New Corridor / Commodity (Problem B, narrow)
**STATUS:** shipped 2026-05-27, byte-equality green (6/6 tests pass; full regression 114/114 + 29 new Iter-4 tests). Added: `vietnam-us.json` corridor, `vietnam-us-textiles.json` commodity leaf, `gtap-references/armington-elasticities.json` (folder + first entry `tex`); `verify_schemas.py` PAIRS extended to 12/12. Iter-4 design choice: tariff inputs held IDENTICAL to india-us-textiles so the only visible corridor-level differentiator is the sovereign spread (BBB-anchor 50/70bps → BB+ at 100/140bps for Vietnam, per S&P affirmation June 28 2025).
**Goal:** prove "any corridor, any commodity" by adding one new corridor without touching code.

**Build:**
- Author one new profile: `config/risk-factor-profiles/export-import/vietnam-us.json` (or `mexico-us.json` — pick one). Cite sources for the Armington, sovereign, WC values per the same schema as `india-us.json`.
- Add the matching row to `config/gtap-references/armington-elasticities.json`.
- Add `test_composer_derived.py` parametrised over both profiles (India-US-tex and the new one).

**Acceptance:**
- New profile runs end-to-end, produces sensible A/B/C.
- The new profile is unit-tested with a known-good fixture (capture the first run's outputs, freeze as the regression fixture for that profile).
- Byte-equality test for India-US-tex still green.

**Demo:** same prompt format, different corridor → recommendation references Vietnam tariffs, not Indian tariffs. Zero Python changes between runs.

---

### ITERATION 5 — Full Provenance Agent (I7)
**STATUS:** shipped 2026-05-27, byte-equality green (6/6 tests pass; full regression 224/224 = Iter-4 baseline 143 + 31 `test_draps_client_extract` + 50 `test_provenance_invariant`; `test_provenance_supplied` stayed at 18 after the Iter-5 in-place rewrite). Added: `draps_client.py` SOFR + fixed-rate extractors (`_extract_sofr_path_from_env`, `_extract_fixed_rate_from_payload`); `provenance.py` REWRITTEN for full I7 (raises `ProvenanceInvariantError` on missing attribution); `test_draps_client_extract.py` + `test_provenance_invariant.py` (NEW). Iter-5 design choices: A1 per-SOFR-point attribution (stamps every point to the profile leaf via `draps_client` extension, not just the driving sources); C2 loan fields use the existing `caller_supplied` source_type with `source_ref` disambiguating from supplied-mode SOFR (no new fourth type — matches the 3-element set in this plan's acceptance); B1 sha256 computed inside N6a (no `profile_resolver.py` change); F1 no `state.hedge_spec_id`-as-filename fallback (the N3b audit_log entry's `output.source` is the sole recovery channel — `hedge_spec_id` is the JSON's spec_id field, not a filename); stamp shape `{field, value, source_type, source_ref, checksum_or_ts}` per detailed-design §2.
**Goal:** turn the Iteration-3 minimal provenance into the full audit — every numeric in `knot_payload` traceable.

**Build:**
- Implement `provenance.py` (N6a) per detailed-design §1 invariant I7: walks `audit_log`, asserts every numeric input has a source, emits the provenance report.
- Wire as the last node before N8 Memory.
- Add `test_provenance_invariant.py` and `test_no_silent_default.py`.

**Acceptance:**
- A run with a missing source attribution raises and fails honestly (no silent pass).
- The provenance report enumerates every numeric in `sofr_path`, the two fixed rates, and the loan fields — each with `source_type` ∈ {`config_file`, `api`, `caller_supplied`} plus its ref/checksum/timestamp.

**Demo:** Provenance panel renders for the India-US-tex run, showing every number's origin file and checksum.

---

### ITERATION 6 — Domestic Services (Problem C, slice 1)
**Goal:** smallest possible domestic-mode end-to-end. Pick services first because it needs the fewest new components.

**Build:**
- Two new components: `components/demand_volatility.py`, `components/payment_cycle.py`. (Reuse the existing `base_sofr.py` and `wc.py`.)
- Author `config/risk-factor-profiles/domestic/us-services.json` and `_base_domestic.json`.
- All component sources resolve to **snapshot files** under `backend/tests/fixtures/snapshots/` — no live API calls in this iteration.
- Extend N1 Intake to extract `business_identity.mode = "domestic_services"`.
- Extend N2 Market-Context to resolve NAICS sector instead of GTAP code when mode is domestic.
- Add `test_composer_derived_domestic.py`.

**Acceptance:**
- Synthetic US SaaS loan → recommendation runs end-to-end.
- Recommendation rationale (from N5) does **not** mention tariff, sovereign, or commodity.
- Provenance report shows `source_type: "snapshot"` with snapshot dates.
- Byte-equality and all previous tests green.

**Demo:** SaaS treasurer prompt → A/B/C with no tariff term, with explanation phrased in "demand volatility / payment cycle" vocabulary.

---

### ITERATION 7 — Domestic Ecommerce (Problem C, slice 2)
**Goal:** the consumer-facing case — adds inventory-cycle dynamics.

**Build:**
- One new component: `components/inventory_carrying.py`.
- Author `config/risk-factor-profiles/domestic/us-ecommerce.json`.
- Still snapshot-mode for data; no live calls.

**Acceptance:**
- Synthetic US ecommerce loan → recommendation reflects inventory-carrying contribution.
- All prior tests green.

**Demo:** ecommerce treasurer prompt → A/B/C that responds to a perturbed inventory-to-sales-ratio snapshot.

---

### ITERATION 8 — First Live Data Binding (FRED)
**Goal:** one real API, end-to-end, with honest failure on outage.

**Build:**
- `data_sources/fred_client.py` + `data_sources/snapshot_cache.py`.
- Bind `base_sofr_fed_path_linear` to FRED at runtime (component file gets a `source.type: "api"` entry).
- Cache policy: configured per profile; default = refresh-on-run, fail-honestly-if-down.
- Add `test_honest_failure.py` covering API outage.

**Acceptance:**
- Live FRED smoke test passes.
- Killing network access → run fails honestly, never silently uses stale data unless the profile authorises it and the provenance report says "stale, as of [date]."
- Offline-mode regression tests (Iterations 1–7) still pass — they continue to use snapshots.

**Demo:** rate refresh from FRED, then disable network and observe honest GIVE-UP rather than wrong-but-confident output.

---

### ITERATION 9 — Census + BLS Live
**Goal:** the rest of the US-domestic data spine.

**Build:**
- `data_sources/census_client.py`, `data_sources/bls_client.py`.
- Re-bind `demand_volatility`, `payment_cycle`, `inventory_carrying` from snapshots to live (each binding's freshness behaviour configured in the component file).

**Acceptance:**
- US-services and US-ecommerce runs use live data, with the provenance report showing each API call's URL + timestamp + response hash.
- Snapshots remain pinned in the fixture folder for CI determinism.

**Demo:** prompt run today → tomorrow → numbers move; provenance trail explains why.

---

### ITERATION 10 — Japan Profile
**Goal:** prove the geographic-portability claim. Japan first because its data is CSV-download not REST — exercises that pattern.

**Build:**
- `data_sources/boj_client.py` (CSV download + parse), `data_sources/meti_client.py`.
- `config/risk-factor-profiles/domestic/jp-services.json` (start with services; ecommerce next iteration if needed).
- Pin a JP-side snapshot in fixtures for CI.

**Acceptance:**
- Synthetic JP SMB loan runs end-to-end with BoJ TONA as the base rate.
- Recommendation vocabulary reflects Japan-specific sources (Tankan, METI).
- Byte-equality test for India-US-tex still green.

**Demo:** JP SaaS loan analysis using TONA-based rates and METI-sourced sentiment.

---

### ITERATION 11 — India Profile
**Goal:** the third geography; also CSV-based.

**Build:**
- `data_sources/rbi_client.py`, `data_sources/mospi_client.py`.
- `config/risk-factor-profiles/domestic/in-services.json`.
- Pin India snapshot.

**Acceptance:**
- Synthetic India SMB loan with MIBOR/repo base, RBI Industrial Outlook for sentiment.
- All prior tests green.

**Demo:** Indian SMB hedge analysis in MIBOR vocabulary — same architecture, different profile.

---

### ITERATION 12 — Frontend Polish (Profile Trace + Provenance Panel)
**Goal:** make the new internals visible to the user.

**Build:**
- `ChatPanel.tsx`: render new SSE events (`profile_resolved`, `spec_resolved`, `composer_completed`, `provenance_emitted`) with the resolution path as a tooltip.
- `ResultsPanel.tsx`: collapsible **Provenance** section showing the audit table.
- API surface adds the SSE events; no shape change to `/run`, `/resume`, `/history`.

**Acceptance:**
- A trace from any of Iterations 1–11 renders with the profile-resolution and provenance details visible to the user.
- No backend churn — pure frontend extension over the V1 Vite/React stack.

**Demo:** end-to-end run with the user clicking into the resolution path and the provenance table.

---

## 2. What is deliberately NOT an iteration here

These are out-of-scope for V2 first release per migration-plan §8 — flagged so I don't sneak them in:

- Hedge-spec variants beyond `_default.json` (`conservative.json`, `opportunistic.json` with 5+ scenarios). Add post-V2 once the 3-mode base is stable.
- Commercial port-congestion feeds (Portcast etc.) — paid; profile-scaffolded but not bound.
- Live tariff feed (USTR / WITS) — profiles read snapshots; live binding is a V3 left-wing extension.
- Portfolio rollup across multiple loans.
- Automated profile generation (LLM authors profiles). Profiles are human-authored in V2.
- New ACTUS contract types beyond PAM + SWAPS.
- DRAPS replacement (Option 2 from detailed-design §6). V2 stays on Option 3.

---

## 3. Critical decisions that must be made BEFORE Iteration 1 ships

Per detailed-design §6 + §8. These are open in the design and need a call:

1. **DRAPS contract dispatch.** Recommended: Option 3 (`dispatch: "draps_v1"` flag on backwards-compat profiles, `"v2_direct"` on new profiles). **Validation step:** read `generalRisk/Backend/src/routes/simulation.routes.ts` and confirm the current contract before writing `draps_client.run_simulation_v2`. If that file's contract differs from what `entAgentProject21/backend/draps_client.py` assumes, this decision changes.
2. **Where snapshot data lives.** Recommended: `backend/tests/fixtures/snapshots/` per project-structure §1. Iteration 6 onward depends on this path being stable.
3. **What "byte-equality" means numerically.** Recommended: SOFR path matches to 4 decimal places (config-architecture §3.1 accepts this); A/B/C totals match exactly. Pin this in `test_byte_equality_v1.py`.

These are flagged as **PROPOSED** in this plan — verify against the V1 codebase before Iteration 1 starts.

---

## 4. Per-iteration test inventory (carryover map)

This shows which tests are added per iteration and which carry forward. Every iteration runs the full accumulated test suite.

| Iteration | Tests added | Cumulative test count |
|---|---|---|
| 1 | `test_byte_equality_v1`, `test_components_unit` (4 V1 ports), copied V1 `test_knot` + `test_wings` | 4 |
| 2 | `test_profile_resolver_layering`, `test_profile_spec_validator`, `test_prompt_boundary`, `test_clean_inputs_gate` | 8 |
| 3 | `test_composer_supplied` | 9 |
| 4 | `test_composer_derived` (parametrised), `test_no_silent_default` | 11 |
| 5 | `test_provenance_invariant` | 12 |
| 6 | `test_composer_derived_domestic`, new `test_components_unit` cases | 13 |
| 7 | extended `test_composer_derived_domestic` | 13 |
| 8 | `test_honest_failure` (FRED-outage scenario) | 14 |
| 9 | extended `test_honest_failure` (Census/BLS) | 14 |
| 10 | JP-profile end-to-end test | 15 |
| 11 | IN-profile end-to-end test | 16 |
| 12 | (frontend visual regression — optional) | 16 |

`test_byte_equality_v1.py` is in the regression set from Iteration 1 onward and must stay green in every subsequent iteration. That is the gate.

---

## 5. How to track progress

Per the V1 discipline of VERIFIED / PROPOSED / OPEN markers:
- Each iteration's deliverables checklist lives in this file.
- When an iteration is shipped, append `STATUS: shipped <date>, byte-equality green` underneath its header.
- Skipped or deferred items become OPEN entries with the reason.

---

**End of design-v1-iteration-plan.md**
