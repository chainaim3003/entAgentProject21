# hedgeAdvisor2 — design-v1-config-architecture

This document is the core of the V2 redesign. It answers the user's direct question: **how many JSON files do we need, what goes in each, and how do we get configurability without breaking the working India-US textile case?**

---

## 1. The one-file V1 reality

**VERIFIED from `generalRisk/Backend/config/simulation/local/supplychain-tariff/supply-chain-tariff-4/SWAPS-1LOAN-WHAT-IF-3-INP-FINAL.json`** (36 KB). The file is a Postman collection. It carries four kinds of content jumbled together:

| Concern | What lives there today |
|---|---|
| **Caller inputs (10 PRIMARY variables)** | exporter_country, importer_country, commodity_code, tariff_current, tariff_peak, loan_notional, loan_start_date, loan_maturity_date, swap_now_offset_months, swap_later_offset_months |
| **GTAP commodity table** | `GTAP_COMMODITIES = {tex: {armington_elasticity: 3.8, ...}, pha: {2.4}, oil: {8.9}}` inline in pre-request JS |
| **Corridor-parameter table** | `CORRIDOR_PARAMETERS = {"India-United States": {...}, "India-United States-tex": {...}, ...}` inline in JS |
| **Risk-factor calibration** | `CALIBRATION = {constant: -35.9048, linear: 133.6627, quadratic: -116.1008}`, `FED_PATH`, `STRESS_TIMING` |
| **Hedge spec** | `swap_now_offset_months=0`, `swap_later_offset_months=3`, `swap_discount_now=100bps`, `swap_discount_later=70bps` |
| **Knot orchestration** | The three POST /eventsBatch calls (Scenarios A, B, C) and how their results are summed |

Each of those six concerns moves on different timescales:

- **Caller inputs** change per request.
- **GTAP table** changes when GTAP releases a new database version (years).
- **Corridor table** changes when geopolitics shifts (e.g. a tariff regime change — months/quarters).
- **Calibration** changes when the academic source paper is revised (years).
- **Hedge spec** is a per-customer-policy decision (rare).
- **Knot orchestration** is the architecture itself (almost never).

V1 ships them in one file because V1 has one customer. V2 splits them along these timescales.

---

## 2. The V2 file layout

```
hedgeAdvisor2/
└── config/
    ├── risk-factor-profiles/                   ── slowest-changing: structural
    │   ├── _base.json                          (defaults; never used alone)
    │   ├── export-import/
    │   │   ├── _base.json                      (export-import common defaults)
    │   │   ├── india-us.json                   (corridor-level: India→US)
    │   │   ├── india-us-textiles.json          (commodity override; PRESERVES V1 numbers)
    │   │   ├── india-us-pharmaceuticals.json   (commodity override; PRESERVES V1 numbers)
    │   │   ├── india-us-oil.json               (commodity override; PRESERVES V1 numbers)
    │   │   ├── vietnam-us.json                 (NEW corridor example)
    │   │   ├── mexico-us.json                  (NEW)
    │   │   └── china-us.json                   (NEW)
    │   └── domestic/
    │       ├── us-ecommerce.json
    │       ├── us-services.json
    │       ├── us-manufacturing.json
    │       ├── jp-ecommerce.json               (Japan expansion; see free-apis.md §5)
    │       ├── jp-services.json
    │       ├── in-ecommerce.json               (India expansion)
    │       └── in-services.json
    │
    ├── risk-factor-components/                 ── medium-changing: model definitions
    │   ├── base_sofr_fed_path_linear.json      (the formula spec + provenance citation)
    │   ├── tariff_gtap_quadratic.json
    │   ├── sovereign_trapezoidal.json
    │   ├── wc_trapezoidal.json
    │   ├── demand_volatility_vix_proxy.json
    │   ├── inventory_carrying_dso_dpo.json
    │   ├── payment_cycle_stress_dso.json
    │   ├── port_congestion_indexed.json        (future, scaffolded)
    │   └── fx_translation_pct_linear.json      (future, scaffolded)
    │
    ├── gtap-references/                        ── fact tables, change when GTAP releases
    │   ├── armington-elasticities.json         (the 65-sector GTAP table - VERIFIED sources)
    │   ├── gtap-sectors.json                   (the 65 sector codes from GTAP 11)
    │   └── README.md                           (data sourcing + last-refreshed dates)
    │
    ├── corridor-references/                    ── fact tables, change with macro/policy
    │   ├── sovereign-ratings.json              (S&P, Moody's, Fitch ratings + spread basis)
    │   ├── policy-rate-paths.json              (Fed, ECB, BoJ, RBI projected paths)
    │   └── README.md
    │
    └── hedge-specs/                            ── per-customer policy
        ├── _default.json                       (3-scenario A/B/C, V1 defaults)
        ├── conservative.json                   (hedge-now-only)
        ├── opportunistic.json                  (5 scenarios incl. swap-at-6mo, swap-at-12mo)
        └── supplied-rates-example.json         (mode=supplied template)
```

**Count answer:** the user asked "do we need additional JSON files." Yes — the V1 single file becomes roughly **15-25 small files** in the V2 layout. The exact count depends on how many new corridors and industries are populated at launch. The minimum to cover V1's existing functionality is **6 files**:
- `risk-factor-profiles/export-import/_base.json`
- `risk-factor-profiles/export-import/india-us.json`
- `risk-factor-profiles/export-import/india-us-textiles.json`
- `risk-factor-profiles/export-import/india-us-pharmaceuticals.json`
- `risk-factor-profiles/export-import/india-us-oil.json`
- `hedge-specs/_default.json`

Plus the 4 component spec files for the V1 formula and the 2 reference tables. **Total minimum: 12 files**, replacing the one 36 KB file.

---

## 3. The byte-equality file — `india-us-textiles.json`

This is the file that proves V2 reproduces V1. Schema first, then the proposed content.

### 3.1 Schema (a profile file)

```jsonc
{
  "$schema": "../../schemas/risk-factor-profile.schema.json",
  "profile_id": "india-us-textiles-v1",
  "version": "1.0.0",
  "mode": "derived",                  // "supplied" | "derived" | "derived_domestic"
  "applies_to": {
    "mode": "export_import",
    "exporter": "IN",                 // ISO codes
    "importer": "US",
    "commodity_gtap": "tex"           // GTAP 65-sector code
  },
  "components": [                     // executed in order, summed additively
    {
      "name": "base_sofr",
      "formula_id": "base_sofr_fed_path_linear",
      "inputs": {
        "initial": 0.0450,
        "peak":    0.0550,
        "final":   0.0475,
        "months_to_peak": 12,
        "total_months_assumption": 24
      },
      "source": {
        "type": "config_file",
        "ref":  "corridor-references/policy-rate-paths.json#US/Fed/2026Q1",
        "note": "VERIFIED: matches V1 inline values from SWAPS-1LOAN-WHAT-IF-3-INP-FINAL.json"
      }
    },
    {
      "name": "tariff",
      "formula_id": "tariff_gtap_quadratic",
      "inputs": {
        "tariff_current_pct": 0.50,
        "tariff_peak_pct":    0.60,
        "armington_elasticity": 3.8,
        "pass_through":         0.20,
        "stress_timing": {
          "months_to_peak":  12,
          "plateau_months":  3,
          "descent_months":  9
        }
      },
      "calibration": {
        "polynomial_kind": "quadratic",
        "coefficients": {
          "constant":  -35.9048,
          "linear":     133.6627,
          "quadratic": -116.1008
        }
      },
      "source": {
        "type": "config_file",
        "ref":  "gtap-references/armington-elasticities.json#tex",
        "citation": "GTAP 11, Corong et al. (2017); Armington Wikipedia median 3.8 (range 2.5-5.1)"
      }
    },
    {
      "name": "sovereign",
      "formula_id": "sovereign_trapezoidal",
      "inputs": {
        "initial": 0.0050,
        "peak":    0.0070,
        "stress_timing": {
          "months_to_peak": 12,
          "plateau_months": 3,
          "descent_months": 9
        }
      },
      "source": {
        "type": "config_file",
        "ref":  "corridor-references/sovereign-ratings.json#IN",
        "citation": "S&P BBB (Aug 2025), 50bps base / 70bps peak per V1 corridor table"
      }
    },
    {
      "name": "wc",
      "formula_id": "wc_trapezoidal",
      "inputs": {
        "initial": 0.0030,
        "peak":    0.0050,
        "stress_timing": {
          "months_to_peak": 12,
          "plateau_months": 3,
          "descent_months": 9
        }
      },
      "source": {
        "type": "config_file",
        "ref":  "(none - V1 inline value)",
        "citation": "V1 textile DSO 60d normal / 90d stressed"
      }
    }
  ],
  "loan_spread_default": 0.025,
  "tenor_grid": {
    "kind": "quarterly",
    "horizon_months": 24,
    "anchor": "loan_start_date"
  }
}
```

**Acceptance:** with this file plus V1's prompt + V1's loan-doc + V2's Composer reading `base_sofr_fed_path_linear`/`tariff_gtap_quadratic`/`sovereign_trapezoidal`/`wc_trapezoidal` formulas that are direct ports of the V1 Postman JS — the produced SOFR path matches V1 to 4 decimal places, and the swap-now and swap-later fixed rates match V1's `swap_now_fixed_rate` and `swap_later_fixed_rate` exactly.

### 3.2 The hedge-spec file `_default.json`

```jsonc
{
  "$schema": "../schemas/hedge-spec.schema.json",
  "spec_id": "default-3-scenario",
  "version": "1.0.0",
  "scenarios": [
    {"id": "A", "label": "No hedge"},
    {"id": "B", "label": "Swap now",        "swap_offset_months": 0},
    {"id": "C", "label": "Swap in 3 months","swap_offset_months": 3}
  ],
  "fixed_rate_rule": "discount_from_path",  // | "supplied" | "market_quote"
  "fixed_rate_params": {
    "swap_now_discount_bps":   100,         // V1 value
    "swap_later_discount_bps":  70          // V1 value
  },
  "contract_template": {
    "loan":  {"actus_type": "PAM", "day_count": "30E360", "payment_cycle": "P3ML1"},
    "swap":  {"actus_type": "SWAPS", "fixed_leg": "PFL", "float_leg": "SOFR"}
  }
}
```

### 3.3 The component file `tariff_gtap_quadratic.json`

```jsonc
{
  "component_id": "tariff_gtap_quadratic",
  "version": "1.0.0",
  "description": "GTAP-grounded tariff component: tariff(t) * Armington * pass_through scaled by a quadratic calibration polynomial in tariff(t).",
  "formula_pseudocode": "gtap_base_bps = (tariff(t) * armington * pass_through) * 100; calib = c0 + c1*tariff(t) + c2*tariff(t)^2; out_bps = gtap_base_bps * calib;",
  "inputs_schema": {
    "tariff_current_pct":  {"type": "number", "min": 0, "max": 5},
    "tariff_peak_pct":     {"type": "number", "min": 0, "max": 5},
    "armington_elasticity":{"type": "number", "min": 0.5, "max": 20},
    "pass_through":        {"type": "number", "min": 0, "max": 1},
    "stress_timing":       {"type": "object"}
  },
  "calibration_schema": {
    "polynomial_kind":     {"const": "quadratic"},
    "coefficients":        {"type": "object",
                            "properties": {"constant": {"type": "number"},
                                           "linear":   {"type": "number"},
                                           "quadratic":{"type": "number"}}}
  },
  "source_citations": [
    "Armington (1969). A Theory of Demand for Products Distinguished by Place of Production. IMF Staff Papers 16(1).",
    "GTAP 11 Database (Corong et al. 2017). Purdue University. https://www.gtap.agecon.purdue.edu/databases/v11/",
    "Wikipedia summary on Armington elasticity median 3.8 across 3,524 estimates (2019 meta-analysis)."
  ]
}
```

The component file is the **executable spec** of the formula; the Composer code is just a dispatch table from `component_id` to a Python function. To audit "what does the tariff component do," a reviewer reads this file plus one Python function — not 800 lines of Postman JS.

---

## 4. Resolution and merge — how a profile gets built at runtime

The Profile-Resolver (N3a) does this for an India-US textile request:

```
1. business_identity = {mode: "export_import", exporter: "IN", importer: "US", commodity_gtap: "tex"}

2. Candidate file list (most-specific first):
     config/risk-factor-profiles/export-import/india-us-textiles.json   ← EXISTS
     config/risk-factor-profiles/export-import/india-us.json            ← EXISTS
     config/risk-factor-profiles/export-import/_base.json               ← EXISTS

3. Load all three (skip any that don't exist).

4. Merge in reverse-priority order (base first, most-specific last):
     merged = deep_merge(_base, india-us, india-us-textiles)
   For scalar keys, later wins. For arrays of components, behavior is:
     - if both have a "components" array, the more-specific overrides component-by-name.
     - components in the more-specific file APPEND if their name isn't in the more-general.
     - this is the V1 corridor-merge behavior, generalised.

5. Record resolution_path = [list of files actually loaded] in audit_log.

6. Return merged profile + resolution_path. The Validator (N3c) does the schema check next.
```

**If NO candidate exists:** return a `profile_errors = ["No risk-factor profile found for IN→US tex. Looked at: ..."]`. The graph routes to GIVE-UP. No silent default.

This is the same Postman JS lookup pattern V1 uses today (general-key, specific-key, DEFAULT, merge), externalised and made auditable.

---

## 5. How configurability is achieved without breaking V1

The byte-equality test from `design-v1-detailed-design.md` §5 is the proof. Concretely:

| User scenario | What V2 does | Why V1 functionality is preserved |
|---|---|---|
| Existing India-US-tex loan | Loads `india-us-textiles.json` (which encodes V1's exact numbers) + `_default.json` hedge spec. Composer runs `derived` mode with the V1 components. | The component formula functions are direct ports of the V1 Postman JS; the profile values are V1 verbatim. Same inputs to ACTUS → same outputs. |
| New corridor (e.g. Vietnam-US apparel) | Author creates `vietnam-us.json` + `vietnam-us-apparel.json`. Composer runs the same `derived` mode with new inputs. | V1 file unchanged. Existing India case unaffected. |
| US ecommerce business | Loads `us-ecommerce.json`. `mode: derived_domestic` triggers components without tariff/sovereign. Composer dispatches to demand_vol / inventory_carrying / wc functions. | V1 file and India profile unchanged. |
| Sophisticated treasurer with own rates | Loads a "supplied" mode profile (or the request itself carries `supplied:` block). Composer pass-through with provenance stamping. | V1 file unchanged. India case unaffected. |
| Treasurer overrides ONE V1 value | Loads V1 profile + a user-supplied override layer. Merge slots the override into the most-specific position. | Original `india-us-textiles.json` unchanged. Only the merged in-memory profile differs. |

The **only way V1 functionality breaks** is if someone edits `india-us-textiles.json`. The migration plan (`design-v1-migration-plan.md`) makes that file read-only-by-policy and lives next to a `india-us-textiles-v1.frozen.json` snapshot that the regression test pins.

---

## 6. Schema files

Each kind of config file has a JSON Schema in `hedgeAdvisor2/schemas/`:

| Schema | Validates |
|---|---|
| `risk-factor-profile.schema.json` | Profile files in `risk-factor-profiles/` |
| `risk-factor-component.schema.json` | Component files in `risk-factor-components/` |
| `hedge-spec.schema.json` | Hedge spec files in `hedge-specs/` |
| `gtap-armington.schema.json` | The GTAP elasticity table file |
| `sovereign-rating.schema.json` | The sovereign rating table file |

The Profile-and-Spec-Validator (N3c) runs these JSON Schema checks plus cross-file checks:
- Every `formula_id` referenced in a profile must exist as a component file.
- Every `inputs.*` key in a profile must satisfy the matching component's `inputs_schema`.
- `mode == "supplied"` requires `supplied.sofr_path[]` and the two fixed rates; `mode == "derived"` requires `components[]`; mutually exclusive.

If any check fails, the run goes to GIVE-UP with the exact failing rule. No silent fix-ups.

---

## 7. The "any business" claim — a worked example

Take a US-based **B2B SaaS** company with a $5M floating-rate revolver financing growth, paying SOFR + 350bps. They want to know whether to lock the rate. They have no tariff exposure, no overseas suppliers.

V2 resolves to:

- `risk-factor-profiles/domestic/us-services.json` — mode `derived_domestic`, components `[base_sofr, demand_volatility, payment_cycle, wc]`.
- `hedge-specs/_default.json` — same A/B/C structure.

The composer produces the SOFR path with `base_sofr` (Fed path, same as V1) + `demand_volatility` (sector-PMI-driven) + `payment_cycle` (B2B DSO stress, sourced from QuickBooks / Atradius surveys cited in the profile) + `wc` (working-capital stress, same shape). No tariff, no sovereign.

DRAPS receives the same kind of payload as V1 (a `sofr_path` and two fixed rates) and produces the same kind of A/B/C totals. The treasurer at the SaaS company gets a recommendation in the **same vocabulary** as the V1 textile exporter — and the architecture didn't change, only a config file was added.

**That is the answer to "configurability and flexibility without breaking current working functionality."** No new code paths; one new file.

---

## 8. The data tables — `armington-elasticities.json`

VERIFIED from GTAP-Purdue: the GTAP 11 database has **65 sectors across 141 countries**. The `gtap-references/armington-elasticities.json` file should contain the full 65-sector table, not the 3-row inline table V1 carries.

Proposed structure (excerpt):

```jsonc
{
  "source": "GTAP 11 Database, Corong et al. (2017)",
  "version_notes": "Median from 2019 meta-analysis of 3,524 estimates: 3.8 (range 2.5-5.1)",
  "url": "https://www.gtap.agecon.purdue.edu/databases/v11/",
  "last_refreshed": "2026-05-23",
  "elasticities": {
    "tex": {"sector_name": "Textiles", "hs_chapters": "50-60", "armington": 3.8, "source_paper": "Corong et al. 2017"},
    "wap": {"sector_name": "Wearing apparel", "hs_chapters": "61-62", "armington": 3.7, "source_paper": "Corong et al. 2017"},
    "pha": {"sector_name": "Chemical, rubber, plastic prods", "hs_chapters": "28-40", "armington": 3.3, "source_paper": "Corong et al. 2017",
             "subsector_overrides": {
                "pharmaceutical": {"armington": 2.4, "source_paper": "Ahmad et al. 2020 (per V1 citation)"}
             }},
    "oil": {"sector_name": "Petroleum oils, crude", "hs_chapters": "27.09", "armington": 8.9, "source_paper": "Khanna et al. 2021 (per V1 citation)"},
    ...  // remaining 60 sectors
  }
}
```

**OPEN:** the actual 65-sector elasticities for GTAP 11 are not free-text on the GTAP website — they require downloading the database. The first cut populates only the 3 V1 sectors (textile, pharma, oil) verbatim, plus the median 3.8 as the "unknown sector" sentinel — **but marked `is_default_sentinel: true` so the Validator can refuse to silently use it for new sectors without an explicit user override**. Adding a new sector means populating its row from a cited source, not borrowing the median.

---

## 9. Summary answer to the user's questions

**Q: Do we need additional JSON files?**
A: Yes — V1's one 36 KB file is split into ~12 minimum files (15-25 typical). The split is along data-update timescales: per-customer hedge spec, per-corridor risk profile, per-formula component spec, per-source reference table.

**Q: How to achieve configurability and flexibility without breaking current working functionality?**
A: Five rules:
1. The byte-equality regression on the India-US-tex case is the gate. No V2 ships without it green.
2. The V1 profile file (`india-us-textiles.json`) is read-only-by-policy and pinned by a frozen snapshot.
3. No silent default-to-textile fallback anywhere. Profile-Resolver returns honest errors when no profile matches.
4. New corridors / industries are new files, not edits to existing files. The merge is layered and order-deterministic.
5. The `mode` flag in a profile (`supplied | derived | derived_domestic`) makes the new audiences live alongside the V1 audience instead of replacing it. The Composer is a dispatch; the profile is the polymorphism.

**End of design-v1-config-architecture.md**
