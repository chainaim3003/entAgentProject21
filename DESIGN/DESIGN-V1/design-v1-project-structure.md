# hedgeAdvisor2 — design-v1-project-structure

V2 file/folder layout. Mirrors `entAgentProject21/` where possible so the team navigates it without re-learning. New folders are clearly marked NEW.

---

## 1. Top-level repo layout

```
hedgeAdvisor2/                                ← repo root
│
├── README.md                                 in-repo overview, points at DESIGN/DESIGN-V1/
├── DESIGN/                                   NEW (already created)
│   └── DESIGN-V1/
│       ├── README.md
│       ├── design-v1-problem-solution-impact.md
│       ├── design-v1-conceptual-design.md
│       ├── design-v1-detailed-design.md
│       ├── design-v1-config-architecture.md
│       ├── design-v1-risk-factor-catalog.md
│       ├── design-v1-free-apis.md
│       ├── design-v1-migration-plan.md
│       └── design-v1-project-structure.md          ← this file
├── DESIGN.md                                 short signpost (like V1's)
├── .gitignore
├── docker-compose.yml                        one-command local start
│
├── config/                                   NEW — the big change vs V1
│   ├── README.md
│   ├── risk-factor-profiles/
│   │   ├── _base.json
│   │   ├── export-import/
│   │   │   ├── _base.json
│   │   │   ├── india-us.json
│   │   │   ├── india-us-textiles.json        BYTE-EQUALITY anchor
│   │   │   ├── india-us-pharmaceuticals.json
│   │   │   ├── india-us-oil.json
│   │   │   ├── vietnam-us.json
│   │   │   ├── mexico-us.json
│   │   │   └── china-us.json
│   │   └── domestic/
│   │       ├── us-ecommerce.json
│   │       ├── us-services.json
│   │       ├── us-manufacturing.json
│   │       ├── jp-ecommerce.json
│   │       ├── jp-services.json
│   │       ├── in-ecommerce.json
│   │       └── in-services.json
│   ├── risk-factor-components/
│   │   ├── base_sofr_fed_path_linear.json
│   │   ├── tariff_gtap_quadratic.json
│   │   ├── sovereign_trapezoidal.json
│   │   ├── wc_trapezoidal.json
│   │   ├── demand_volatility_vix_proxy.json
│   │   ├── inventory_carrying_dso_dpo.json
│   │   ├── payment_cycle_stress_dso.json
│   │   ├── port_congestion_indexed.json
│   │   ├── fx_translation_pct_linear.json
│   │   └── input_cost_passthrough_linear.json
│   ├── gtap-references/
│   │   ├── README.md
│   │   ├── armington-elasticities.json
│   │   └── gtap-sectors.json
│   ├── corridor-references/
│   │   ├── README.md
│   │   ├── sovereign-ratings.json
│   │   └── policy-rate-paths.json
│   ├── hedge-specs/
│   │   ├── _default.json
│   │   ├── conservative.json
│   │   ├── opportunistic.json
│   │   └── supplied-rates-example.json
│   └── _quarantine/                          rollback bucket; resolver ignores
│       └── README.md
│
├── schemas/                                  NEW — JSON Schemas
│   ├── risk-factor-profile.schema.json
│   ├── risk-factor-component.schema.json
│   ├── hedge-spec.schema.json
│   ├── gtap-armington.schema.json
│   └── sovereign-rating.schema.json
│
├── backend/                                  Python, FastAPI + LangGraph
│   ├── main.py                               from V1, unchanged
│   ├── api.py                                from V1, extended
│   ├── config.py                             from V1, extended (+ CONFIG_DIR)
│   ├── graph.py                              from V1, rewired (5 new nodes)
│   ├── gemini_client.py                      from V1, unchanged
│   ├── draps_client.py                       from V1, + run_simulation_v2()
│   ├── actus_mentor_client.py                from V1, unchanged
│   ├── memory_store.py                       from V1, unchanged
│   ├── reasoning_agents.py                   from V1, intake + market_context extended
│   ├── deterministic_agents.py               from V1, unchanged
│   ├── explanation_agent.py                  from V1, unchanged
│   │
│   ├── profile_resolver.py                   NEW — N3a
│   ├── hedge_spec_resolver.py                NEW — N3b
│   ├── profile_spec_validator.py             NEW — N3c
│   ├── composer.py                           NEW — N3d
│   ├── provenance.py                         NEW — N6a
│   ├── components/                           NEW module
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── base_sofr.py
│   │   ├── tariff.py                         direct port of V1 calcTariffComponent
│   │   ├── sovereign.py                      direct port of V1 calcSovereign
│   │   ├── wc.py                             direct port of V1 calcWC
│   │   ├── demand_volatility.py
│   │   ├── inventory_carrying.py
│   │   ├── payment_cycle.py
│   │   ├── port_congestion.py
│   │   ├── fx_translation.py
│   │   └── input_cost_passthrough.py
│   ├── data_sources/                         NEW — bind components to free APIs
│   │   ├── __init__.py
│   │   ├── fred_client.py                    federalreservebank-of-st-louis
│   │   ├── census_client.py
│   │   ├── bls_client.py
│   │   ├── bea_client.py
│   │   ├── eia_client.py
│   │   ├── comtrade_client.py
│   │   ├── wits_client.py
│   │   ├── ny_fed_gscpi_client.py
│   │   ├── boj_client.py                     Japan
│   │   ├── rbi_client.py                     India
│   │   ├── meti_client.py                    Japan
│   │   ├── mospi_client.py                   India
│   │   └── snapshot_cache.py                 the offline-mode cache
│   │
│   ├── requirements.txt                      + jsonschema, + cachetools
│   ├── .env.example                          V1 vars + new CONFIG_DIR, FRED_API_KEY, CENSUS_API_KEY, BLS_API_KEY, BEA_API_KEY, EIA_API_KEY, COMTRADE_API_KEY
│   │
│   └── tests/
│       ├── test_knot.py                      from V1, unchanged
│       ├── test_wings.py                     from V1, unchanged
│       ├── test_byte_equality_v1.py          NEW — the gate
│       ├── test_profile_resolver.py          NEW
│       ├── test_profile_spec_validator.py    NEW
│       ├── test_composer_supplied.py         NEW
│       ├── test_composer_derived.py          NEW
│       ├── test_composer_derived_domestic.py NEW
│       ├── test_components_unit.py           NEW
│       ├── test_provenance_invariant.py      NEW
│       ├── test_prompt_boundary.py           NEW — invariant I1 grep-style
│       ├── test_clean_inputs_gate.py         NEW — invariant I2
│       ├── test_honest_failure.py            NEW — invariant I5
│       ├── test_no_silent_default.py         NEW
│       └── fixtures/
│           ├── v1-baseline/
│           │   └── india-us-textiles.json    captured V1 SOFR + fixed + A/B/C
│           ├── snapshots/
│           │   ├── fred/                     point-in-time snapshots for offline tests
│           │   ├── census/
│           │   └── bls/
│           └── profiles/                     copies of authored profiles pinned for tests
│
├── frontend/                                 from V1, extended
│   ├── package.json, vite.config.ts, etc.
│   └── src/
│       ├── main.tsx                          unchanged
│       ├── App.tsx                           unchanged
│       ├── api.ts                            + supplied-rates request shape
│       ├── ChatPanel.tsx                     + profile-trace events render
│       ├── ResultsPanel.tsx                  + provenance report panel
│       └── index.css                         unchanged
│
└── scripts/                                  NEW
    ├── capture_v1_baseline.py                runs V1 once, writes the fixture
    ├── refresh_snapshots.py                  pulls fresh data into fixtures/snapshots/
    └── validate_all_profiles.py              CI helper: runs Profile-Spec-Validator over every config file
```

---

## 2. File-count summary

| Category | V1 count | V2 count | Delta |
|---|---|---|---|
| Backend Python source | 11 | 25 | +14 (profile/spec/composer/components/data_sources) |
| Backend tests | 2 | 14 | +12 |
| Frontend source | 6 | 6 | 0 (UI extensions are in-place) |
| Frontend config | 4 | 4 | 0 |
| Config (JSON) | 0 | 25-40 | +25 to +40 (the polymorphism layer) |
| Schemas | 0 | 5 | +5 |
| Scripts | 0 | 3 | +3 |
| Root config | 4 | 4 | 0 |
| Design docs | 5 | 8 | +3 |
| **Total** | **32** | **~94** | **+62** |

The file count roughly triples. Most of the growth is in `config/` — JSON files that are **data, not code**, and that's the point: making the polymorphism layer authored in data is what makes "any business in any corridor" possible without rewriting code.

---

## 3. How the layout enforces the design's invariants

- **I1 (prompt boundary):** `grep -nl "prompt" backend/composer.py backend/profile_resolver.py backend/hedge_spec_resolver.py backend/profile_spec_validator.py backend/components/*.py` must return zero matches. CI check.
- **I2 (clean-inputs gate):** `grep -nl "validated_inputs\\|knot_payload" backend/*.py` must show exactly one producer and one consumer for each. CI check.
- **I6 (profile boundary):** Only `profile_resolver.py` and `hedge_spec_resolver.py` import from a path containing `config/`. CI check.
- **I7 (provenance):** `provenance.py`'s assertion that every numeric in `knot_payload` has an entry in `audit_log["sources"]` is the runtime check.

Each of these is a 1-line grep, the same auditability test V1 already pioneered.

---

## 4. What this layout deliberately avoids

- **No `services/` layer.** Same as V1 — clients are the services.
- **No `models/` package.** Pydantic state types live next to where they're used (`graph.py` for the state, schemas in JSON for everything else).
- **No god-file `risk_engine.py`.** The Composer is a 250-line dispatch; the work is in the `components/` directory, one file per formula.
- **No mock or fake config files.** Every JSON file in `config/` is real config, used at runtime. Test fixtures live separately under `backend/tests/fixtures/`.
- **No "default" silent fallback profile.** The `_base.json` files are merge sources, not standalone profiles — the Resolver will not return `_base.json` as a result on its own; it always needs at least one corridor or industry file to be present.

---

## 5. Backend API surface (unchanged from V1 in shape, extended in body)

| Method | Path | V2 changes |
|---|---|---|
| POST | `/run` | Request body now accepts either `{prompt, loan_doc}` (V1 shape, still supported) OR `{prompt, loan_doc, supplied: {sofr_path, swap_now_fixed, swap_later_fixed}}` OR `{prompt, loan_doc, profile_override: {...}}` |
| GET | `/trace` | Same SSE format; new event types appear: `profile_resolved`, `spec_resolved`, `composer_completed`, `provenance_emitted` |
| POST | `/resume` | Unchanged |
| GET | `/history` | Same shape; the response now includes the resolved `profile_id` and `spec_id` per past run |

Both V1 callers and V2 callers work — V1 callers see the V1 fields, V2 callers see V2 fields. Backwards-compatible JSON additions only.

---

## 6. The frontend — minimal-change pattern

The bow-tie trace in `ChatPanel.tsx` already renders an ordered list of node completions. V2 adds entries to the list — five new node types — without changing the rendering primitive. The Profile-Resolver event includes `resolution_path: [files]` which the panel renders as a tooltip on the node row.

`ResultsPanel.tsx` gets one new collapsible section: **Provenance**. It shows the audit table from N6a — every numeric input → source. This is the user-visible payoff of invariant I7.

No new dependencies. No new build config. The V1 Vite + React + Tailwind stack stays.

---

## 7. Dependencies — new requirements

V1 requirements + these additions:

```
jsonschema>=4.20.0        # for Profile-Spec-Validator
cachetools>=5.3.0         # for data_sources/snapshot_cache.py
httpx>=0.27.0             # already V1; bump if older
pandas>=2.2.0             # ONLY if data_sources/* parsing CSVs from BoJ/RBI
                          # (Python stdlib csv is enough for V2 first cut; defer pandas)
```

`pandas` is deliberately *not* added in the first cut. Stdlib `csv` + dict comprehensions handle the BoJ / RBI CSV downloads. We keep the dependency tree small.

---

## 8. Docker / docker-compose

The V1 `docker-compose.yml` becomes V2's `docker-compose.yml` with:
- one new volume mount for `./config:/app/config:ro` (read-only — V2 doesn't write to config at runtime)
- one new env var injection for `CONFIG_DIR=/app/config`

Snapshot data lives under `backend/tests/fixtures/snapshots/` and is mounted only for the offline-mode tests, not in production.

---

**End of design-v1-project-structure.md**
