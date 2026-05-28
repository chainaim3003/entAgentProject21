# hedgeAdvisor2 — design-v1-migration-plan

This document specifies how to bring up V2 in `hedgeAdvisor2/` **without breaking anything in V1's `entAgentProject21/`**, and the order in which the V2 work happens.

---

## 0. The bright-line rule

**`entAgentProject21/` is not edited.** V2 lives in `hedgeAdvisor2/`. Code is copied (not moved or symlinked) so V1 keeps running. The two projects share `generalRisk` (DRAPS) and `ACTUS-MENTOR-MCP` as external dependencies — that is unchanged.

---

## 1. The byte-equality gate (the non-negotiable test)

Before any V2 feature is declared shipped:

1. **Capture V1 ground truth.** Run `entAgentProject21/backend` with the V1 demo prompt + sample loan; record:
   - the resolved `validated_inputs` (full dict)
   - the `sofr_path` that DRAPS used (intercept via logging if needed)
   - the `swap_now_fixed_rate`, `swap_later_fixed_rate`
   - the A_total, B_total, C_total
   - the events list digest (e.g. sha256 of the canonical JSON serialisation)
2. **Persist as fixture.** Save under `hedgeAdvisor2/backend/tests/fixtures/v1-baseline/india-us-textiles.json`. This is the regression target.
3. **Run V2.** With the V1 prompt + loan-doc, V2 reads `config/risk-factor-profiles/export-import/india-us-textiles.json` (which encodes V1's exact constants), runs the V2 Composer, calls DRAPS.
4. **Assert byte equality on all four artifacts** above. If any differs by more than the 4-decimal-place tolerance documented in `design-v1-detailed-design.md` §5, V2 fails. No exceptions, no waivers.

Until this test is green, nothing else in V2 ships.

---

## 2. Code reuse from V1 — what copies in unchanged

Verbatim copies from `entAgentProject21/backend/` to `hedgeAdvisor2/backend/`:

| V1 file | V2 file | Reason |
|---|---|---|
| `main.py` | `main.py` | FastAPI bootstrap; identical |
| `api.py` | `api.py` | 4 routes; identical (extends if new inputs needed) |
| `config.py` | `config.py` | Env vars; extends with `CONFIG_DIR` for the new layout |
| `gemini_client.py` | `gemini_client.py` | Unchanged |
| `actus_mentor_client.py` | `actus_mentor_client.py` | Unchanged |
| `memory_store.py` | `memory_store.py` | Unchanged (V2 stores more fields; the store is field-agnostic) |
| `explanation_agent.py` | `explanation_agent.py` | Unchanged |

Files that get small additive edits (existing logic preserved, new behavior gated by config):

| V1 file | V2 changes |
|---|---|
| `reasoning_agents.py` (N0/N1/N2/N5 prompts) | Extend N1 schema to extract `business_identity` (industry/country/mode). Extend N2 to resolve sector code (NAICS for domestic, GTAP for export-import). Same Gemini calls, broader output. |
| `deterministic_agents.py` | Keep N3/N4/N6/N8/NX exactly as is. **Add new files** rather than editing this one — see §3. |
| `graph.py` | Add 5 new nodes, rewire the linear edges between N3 and N4 to pass through N3a→N3b→N3c→N3d. V1 conditional retry at N3 unchanged. Add new conditional at N3c (pass/fail, no retry). |
| `draps_client.py` | Add a second function `run_simulation_v2(knot_payload)` that handles the V2 payload shape; keep `run_simulation(validated_inputs)` exactly as V1. The Simulation node calls whichever matches the resolved profile's `dispatch` flag (see `design-v1-detailed-design.md` §6 Option 3). |

V1 tests under `entAgentProject21/backend/tests/` are copied into `hedgeAdvisor2/backend/tests/` and **must continue to pass** alongside the new V2 tests.

---

## 3. New code — what V2 adds (the new files)

```
hedgeAdvisor2/backend/
├── profile_resolver.py            (N3a)  ~150 lines
├── hedge_spec_resolver.py         (N3b)  ~80 lines
├── profile_spec_validator.py      (N3c)  ~200 lines  (JSON Schema + cross-file checks)
├── composer.py                    (N3d)  ~250 lines
├── components/                    component formula functions (NEW MODULE)
│   ├── __init__.py
│   ├── registry.py                (formula_id → function dispatch)
│   ├── base_sofr.py
│   ├── tariff.py                  (direct port of V1 calcTariffComponent)
│   ├── sovereign.py               (direct port of V1 calcSovereign)
│   ├── wc.py                      (direct port of V1 calcWC)
│   ├── demand_volatility.py
│   ├── inventory_carrying.py
│   ├── payment_cycle.py
│   ├── port_congestion.py
│   ├── fx_translation.py
│   └── input_cost_passthrough.py
├── provenance.py                  (N6a)  ~120 lines
└── tests/
    ├── test_byte_equality_v1.py   THE GATE — see §1
    ├── test_profile_resolver.py
    ├── test_composer_modes.py
    ├── test_components.py         per-component unit tests
    └── fixtures/
        ├── v1-baseline/india-us-textiles.json
        └── profiles/              snapshot copies of every profile for fixture-based tests
```

Plus the entire `config/` tree from `design-v1-config-architecture.md` §2.

**Total new code estimate: ~1200 LOC of Python + ~12-25 JSON config files (~200-500 lines each).** The Python LOC is comparable to V1's backend total — V2 doubles the codebase, which is in line with doubling the functional surface.

---

## 4. Phase order

### Phase 0 — Scaffold + byte-equality (week 1)
- Copy V1 files into `hedgeAdvisor2/backend/`.
- Capture V1 ground truth → `tests/fixtures/v1-baseline/`.
- Write `india-us-textiles.json` profile + the 4 V1 component files.
- Port the 4 V1 formulas to `components/*.py` as direct translations of the Postman JS.
- Build a minimal `composer.py` that runs `derived` mode only.
- Stub `profile_resolver.py`, `hedge_spec_resolver.py`, `profile_spec_validator.py`.
- Wire into `graph.py`.
- **Gate:** `test_byte_equality_v1.py` passes.

### Phase 1 — Supplied mode (week 2)
- Add `mode: supplied` handling in the composer.
- Add `supplied-rates-example.json` hedge-spec template.
- Add an API extension on `POST /run` to accept a `supplied:` block in the request body (alternative to the prompt + loan-doc shape).
- Tests: a supplied-rates request produces A/B/C totals identical to a manually-computed reference.
- **Gate:** byte-equality test still green; new supplied test passes.

### Phase 2 — Domestic mode (week 3)
- Add `mode: derived_domestic`, the new component functions (demand_volatility, inventory_carrying, payment_cycle).
- Author `us-ecommerce.json`, `us-services.json` profiles.
- Bind components to FRED + Census + BLS APIs **in offline-snapshot mode first** (component file points at a static snapshot dated).
- Tests: end-to-end for a synthetic US ecommerce loan; check the recommendation makes directional sense (no tariff term in the explanation, presence of demand-vol term).
- **Gate:** all prior tests green; new domestic test passes.

### Phase 3 — Live API binding (week 4)
- Switch the bound components from snapshot to live FRED / Census / BLS.
- Implement freshness checks + honest-failure on API unavailability.
- Provenance Agent (N6a) emits the full source attribution.
- Tests: live-binding integration test, run daily on CI.

### Phase 4 — Japan / India profiles (weeks 5-6)
- Author `jp-ecommerce.json`, `jp-services.json`, `in-ecommerce.json`, `in-services.json`.
- Bind BoJ / RBI / METI / MOSPI sources (mostly CSV download patterns, not REST).
- Tests: end-to-end for synthetic JP and IN loans.

### Phase 5 — Frontend updates (week 7)
- Extend `ChatPanel` to surface the resolved profile in the live trace ("loaded profile: india-us-textiles-v1, components: [base_sofr, tariff, sovereign, wc]").
- Extend `ResultsPanel` to render the provenance report.
- Pure UI work; no backend churn.

---

## 5. Rollback plan

If a V2 feature breaks something downstream (DRAPS, ACTUS-Mentor):

1. The V1 codebase is untouched — `entAgentProject21/` keeps serving.
2. V2's offending profile file is moved to `config/_quarantine/`. The Resolver's candidate list does not look there.
3. V2 continues to serve the unaffected profiles.
4. A failing profile is a config problem, not a code problem; root-cause and re-deploy the profile file.

The architecture's failure mode is **per-profile** by design.

---

## 6. What can break, what cannot

**CAN break safely (V1 keeps running):**
- Any new V2 profile file with a bug → that profile's runs Give-Up, others fine.
- A live API outage → bound component fails honestly for affected profiles; profiles without that binding are unaffected.
- Frontend bug in V2 → V1 frontend at `entAgentProject21/frontend/` still works.

**CANNOT break — the regression gate enforces:**
- The India-US-tex byte-equality test.
- The V1 demo prompt → recommendation path.

**OPEN risk to track explicitly:**
- DRAPS contract evolution. If `generalRisk/Backend/src/routes/simulation.routes.ts` changes shape (independently of V2), V2's draps_client and V1's draps_client both need updating. They are independent files in independent projects; either project's developers must communicate this.

---

## 7. Tests required before V2 is signed off

| Test name | What it asserts | Gate? |
|---|---|---|
| `test_byte_equality_v1.py` | V1 demo prompt → V2 produces identical SOFR path, fixed rates, A/B/C | **Yes — required for any release** |
| `test_profile_resolver_layering.py` | base + corridor + commodity merge order, missing-file behavior | yes |
| `test_profile_spec_validator.py` | JSON Schema checks, cross-file checks, mode constraints | yes |
| `test_composer_supplied.py` | mode=supplied: caller numbers passed through, provenance stamped | yes |
| `test_composer_derived.py` | mode=derived: byte-equality vs known fixture for each authored profile | yes |
| `test_composer_derived_domestic.py` | mode=derived_domestic: directional checks (no tariff term, etc.) | yes |
| `test_components_unit.py` | Each component function: known inputs → known outputs | yes |
| `test_provenance_invariant.py` | Every numeric knot input has an audit_log source attribution (I7) | yes |
| `test_prompt_boundary.py` | grep-style: N3a/b/c/d/4 never read `prompt` (I1 preserved) | yes |
| `test_clean_inputs_gate.py` | `validated_loan`, `knot_payload` each have exactly one producer & consumer (I2) | yes |
| `test_honest_failure.py` | Missing profile, missing API key, malformed config all reach Give-Up cleanly (I5) | yes |
| `test_no_silent_default.py` | No profile-resolver fallback to a default profile; explicit absence required | yes |

The V1 test files (`test_knot.py`, `test_wings.py`) are also retained and run as part of the V2 test suite.

---

## 8. What is NOT in scope for V2 first release

Carrying forward V1's discipline:

- **No CI/CD config beyond a local pytest runner.** Deployment is a Phase 5+ concern.
- **No multi-tenancy.** One thread at a time.
- **No real-time API streaming feeds.** Components read snapshots or pull-on-demand with caching.
- **No portfolio rollup.** One loan per run. Portfolio aggregation is a V3 right-wing extension.
- **No new ACTUS contract types.** PAM + SWAPS only, same as V1.
- **No DRAPS replacement.** Even though the user could replace it (Option 2 in `design-v1-detailed-design.md` §6), V2 starts on Option 3 to keep V1 byte-equality automatic.

---

**End of design-v1-migration-plan.md**
