# hedgeAdvisor2 — design-v1-detailed-design

## 1. Textual graph — V2 nodes and edges

V1 nodes preserved verbatim; new nodes prefixed `N3a/N3b/N3c/N3d/N6a`.

```
================================================================================
  hedgeAdvisor2 (V2) - TEXTUAL GRAPH :: agents and edges
================================================================================

NODES
=====

  N0   ORCHESTRATOR              reasoning (Gemini Pro)        UNCHANGED
  N1   INTAKE                    reasoning (Gemini)            EXTENDED  *
  N2   MARKET-CONTEXT            reasoning (Gemini)            EXTENDED  *
  N3   INPUT-VALIDATOR           DETERMINISTIC                 UNCHANGED
  N3a  RISK-FACTOR-PROFILE-RES   DETERMINISTIC                 NEW
  N3b  HEDGE-SPEC-RESOLVER       DETERMINISTIC                 NEW
  N3c  PROFILE-AND-SPEC-VALID    DETERMINISTIC                 NEW
  N3d  RISK-FACTOR-COMPOSER      DETERMINISTIC                 NEW
  N4   SIMULATION                DETERMINISTIC (DRAPS)         UNCHANGED **
  N5   INTERPRETATION            reasoning (Gemini)            EXTENDED  *
  N6   DISCLOSURE                DETERMINISTIC                 UNCHANGED
  N6a  PROVENANCE                DETERMINISTIC                 NEW
  N7   EXPLANATION (optional)    reasoning (RAG)               UNCHANGED
  N8   MEMORY                    DETERMINISTIC                 EXTENDED  *
  NX   GIVE-UP                   DETERMINISTIC                 UNCHANGED

  *  EXTENDED = same agent type, broader input/output schema
  ** UNCHANGED at the agent level; DRAPS input contract may need extension - see §6


EDGES (the V2 flow)
===================

  edge        from                    to                      carries
  -------------------------------------------------------------------------------
  e0   START                          N0   ORCHESTRATOR        prompt, loan_doc
  e1   N0   ORCHESTRATOR               N1   INTAKE              prompt, loan_doc
  e2   N1   INTAKE                     N2   MARKET-CONTEXT      raw_inputs + identity
  e3   N2   MARKET-CONTEXT             N3   INPUT-VALIDATOR     raw_inputs + market_context
  e4   N3   INPUT-VALIDATOR            N3a  PROFILE-RESOLVER    validated_loan          [PASS]
  e5   N3   INPUT-VALIDATOR            N1   INTAKE              validation_errors       [RETRY]
  e6   N3   INPUT-VALIDATOR            NX   GIVE-UP             validation_errors       [FAIL]
  e7   N3a  PROFILE-RESOLVER           N3b  HEDGE-SPEC-RES      resolved_risk_profile
  e8   N3b  HEDGE-SPEC-RES             N3c  PROFILE-SPEC-VALID  resolved_risk_profile + resolved_hedge_spec
  e9   N3c  PROFILE-SPEC-VALID         N3d  COMPOSER            validated_profile + validated_spec   [PASS]
  e10  N3c  PROFILE-SPEC-VALID         NX   GIVE-UP             profile_errors / spec_errors          [FAIL]
       (retry edge OPEN - see §7. First version: no retry, straight to GIVE-UP. Profile/spec
        errors are config-file problems, not LLM-extraction problems, so retry won't help.)
  e11  N3d  COMPOSER                   N4   SIMULATION          knot_payload
                                                                  { sofr_path,
                                                                    swap_now_fixed,
                                                                    swap_later_fixed,
                                                                    loan_fields,
                                                                    provenance }
  e12  N4   SIMULATION                 N5   INTERPRETATION      simulation_result
  e13  N5   INTERPRETATION             N6   DISCLOSURE          recommendation
  e14  N6   DISCLOSURE                 N6a  PROVENANCE          disclosure_doc
  e15  N6a  PROVENANCE                 N8   MEMORY              provenance_report
  e16  N7   EXPLANATION                (out-of-band)            side query
  e17  N8   MEMORY                     END
  e18  NX   GIVE-UP                    END


THE STRUCTURAL LINES (preserved from V1 + extended)
===================================================

  PROMPT BOUNDARY  (I1)
    Only N0, N1, N2 ever see `prompt`.
    N3a, N3b, N3c, N3d, N4 read only structured state from upstream.
    NEW: N3a reads `business_identity + corridor + commodity` to pick profile file;
         it does NOT read prompt to do that picking. Grep audit.

  CLEAN-INPUTS GATE  (I2)
    `validated_loan` produced only by N3, consumed by N3a, N3b.
    `validated_profile + validated_spec` produced only by N3c, consumed by N3d.
    `knot_payload` produced only by N3d, consumed by N4.
    NEW: N4 still has exactly one producer. The change is that producer is now
         N3d (which gates on N3c) rather than N3 directly. Two boundaries in
         series, both deterministic.

  PROFILE BOUNDARY  (I6 - NEW)
    A risk-factor profile or hedge-spec is loaded ONLY by N3a / N3b from
    `config/risk-factor-profiles/` or `config/hedge-specs/`. No other node
    reads those folders. Grep audit.

  PROVENANCE INVARIANT  (I7 - NEW)
    Every numeric input to N4 traces in `audit_log` to one of:
      (a) a config file path + sha256 checksum,
      (b) a free-API URL + timestamp + response sha256,
      (c) a caller-supplied input + the message/field where it arrived.
    N6a verifies this at run-time; if a knot input has no source, it raises
    and the run fails. This is what makes Problem A (supplied SOFR) safe.


CONDITIONAL ROUTING
===================

  at N3 INPUT-VALIDATOR (UNCHANGED from V1):
      errors empty                       -> e4  -> N3a
      errors AND retries < MAX           -> e5  -> N1   (bounded)
      errors AND retries >= MAX          -> e6  -> NX

  at N3c PROFILE-AND-SPEC-VALIDATOR (NEW):
      errors empty                       -> e9  -> N3d
      errors not empty                   -> e10 -> NX
        (no retry - config errors are not extraction errors)

  everywhere else: single deterministic outgoing edge.


ZONES
=====

  control plane     = { N0 }
  left wing         = { N1, N2 }                  (reasoning)
  left wing config  = { N3a, N3b, N3c, N3d }      (deterministic, NEW group)
  boundary          = { N3 } + N3c                (deterministic gates)
  KNOT              = { N4 }                      (deterministic core)
  right wing        = { N5, N6, N6a, N7 }         (mix)
  feedback loop     = { N8 }                      (deterministic)
  failure path      = { NX }                      (deterministic)

================================================================================
```

---

## 2. State schema — diff from V1

V1 `HedgeAdvisorState` is preserved; new fields are added.

```python
class HedgeAdvisorStateV2(TypedDict, total=False):
    # ─── UNCHANGED from V1 ───
    prompt: str
    private_loan_doc: str
    thread_id: str
    raw_inputs: dict | None
    market_context: dict | None
    validated_inputs: dict | None              # renamed in V2: validated_loan
    validation_errors: list[str]
    retry_count: int
    simulation_result: dict | None
    recommendation: dict | None
    disclosure_doc: dict | None
    memory_record_id: str | None
    failure: dict | None
    audit_log: Annotated[list[dict], operator.add]

    # ─── NEW in V2 ───
    business_identity: dict | None
        # { industry: str, country: str, mode: "export_import" | "domestic_ecommerce" |
        #   "domestic_services" | "domestic_manufacturing", subsector: str | None }

    risk_factor_profile_id: str | None         # produced by N3a, e.g. "india-us-textiles-v1"
    resolved_risk_profile: dict | None         # the loaded profile file contents
    profile_resolution_path: list[str]         # which files were merged (general + override)

    hedge_spec_id: str | None
    resolved_hedge_spec: dict | None

    profile_errors: list[str]
    spec_errors: list[str]

    knot_payload: dict | None                  # produced by N3d, consumed by N4
        # { sofr_path: list[{time, value}],
        #   swap_now_fixed: float,
        #   swap_later_fixed: float,
        #   loan: {...},
        #   provenance: [{field, source_type, source_ref, checksum_or_ts}] }

    provenance_report: dict | None             # produced by N6a
```

The V1 `validated_inputs` field is preserved (renamed `validated_loan` in V2 only at the variable name level; the dict shape is the same). Existing tests against V1 state shape continue to pass — V2 fields are additive.

---

## 3. The Composer (N3d) algorithm

Pseudocode, intentionally short. The real code lives in `backend/composer.py`.

```python
def compose(validated_loan, validated_profile, validated_spec) -> knot_payload:
    mode = validated_profile["mode"]                # "supplied" | "derived" | "derived_domestic"
    provenance = []

    if mode == "supplied":
        sofr_path = validated_profile["supplied"]["sofr_path"]
        swap_now_fixed = validated_spec["supplied"]["swap_now_fixed_rate"]
        swap_later_fixed = validated_spec["supplied"]["swap_later_fixed_rate"]
        provenance += stamp_supplied(validated_profile, validated_spec)

    elif mode in ("derived", "derived_domestic"):
        components = validated_profile["components"]
        # Each component spec: {name, formula_id, inputs:{...}, calibration:{...}, source:{...}}
        sofr_path = []
        for t in tenor_grid(validated_loan, validated_spec):
            total_bps = 0.0
            for c in components:
                fn = COMPONENT_REGISTRY[c["formula_id"]]
                value_bps = fn(c["inputs"], c["calibration"], t)
                total_bps += value_bps
                provenance.append({"field": f"sofr[{t}].{c['name']}",
                                   "source_type": c["source"]["type"],
                                   "source_ref": c["source"]["ref"]})
            sofr_path.append({"time": t, "value": total_bps / 10000.0})

        # Fixed-rate rule from hedge-spec
        rule = validated_spec["fixed_rate_rule"]      # "discount_from_path" | "supplied" | "market_quote"
        swap_now_fixed = apply_fixed_rate_rule(rule, sofr_path, validated_spec["swap_now_offset_months"])
        swap_later_fixed = apply_fixed_rate_rule(rule, sofr_path, validated_spec["swap_later_offset_months"])

    else:
        raise ConfigError(f"unknown mode: {mode}")

    return {
        "sofr_path": sofr_path,
        "swap_now_fixed": swap_now_fixed,
        "swap_later_fixed": swap_later_fixed,
        "loan": validated_loan,
        "provenance": provenance,
    }
```

`COMPONENT_REGISTRY` holds the deterministic formula functions:

| `formula_id` | Function | Notes |
|---|---|---|
| `base_sofr_fed_path_linear` | linear interpolation between `initial`, `peak`, `final` with `months_to_peak`. | Mirrors V1's `calcBaseSofr`. Inputs come from the profile, not hardcoded. |
| `tariff_gtap_quadratic` | `(tariff(t) × armington × pass_through) × calib_polynomial(tariff(t))`. | Mirrors V1's `calcTariffComponent`. Calibration polynomial coefficients are inputs from the profile, not constants in code. |
| `sovereign_trapezoidal` | rise to peak, plateau, descent to initial. | Mirrors V1's `calcSovereign`. |
| `wc_trapezoidal` | same shape as sovereign with different bands. | Mirrors V1's `calcWC`. |
| `demand_volatility_vix_proxy` *(new for domestic)* | proxies demand volatility from VIX or sector-PMI. See §4. |
| `inventory_carrying_dso_dpo` *(new for domestic)* | working-capital stress from DSO/DPO/DIO gap. |
| `payment_cycle_stress_dso` *(new for domestic)* | late-payment-rate-driven stress. |
| `port_congestion_indexed` *(future)* | port congestion index from NY Fed GSCPI or World Bank CPPI. |
| `fx_translation_pct_linear` *(future)* | FX-spot move × translated-revenue share. |

Each function has a one-to-one mapping with a piece of the V1 inline JS. The first four together — under the **right profile inputs** — must reproduce V1's output byte-for-byte.

---

## 4. The Resolver (N3a) algorithm

```python
def resolve_risk_profile(business_identity, market_context) -> resolved_profile:
    mode = business_identity["mode"]
    
    if mode == "export_import":
        # priority lookup: most-specific first, then general, then base
        candidates = [
            f"export-import/{exporter}-{importer}-{commodity}.json",     # e.g. india-us-tex.json
            f"export-import/{exporter}-{importer}.json",                  # india-us.json
            f"export-import/_base.json",                                   # base export-import
        ]
    elif mode == "domestic_ecommerce":
        candidates = [
            f"domestic/{country}-ecommerce-{subsector}.json",
            f"domestic/{country}-ecommerce.json",
            f"domestic/_ecommerce_base.json",
        ]
    elif mode == "domestic_services":
        candidates = [...]
    elif mode == "domestic_manufacturing":
        candidates = [...]
    else:
        return ProfileErrors([f"unknown mode: {mode}"])

    # Load each file that exists; merge in order (most-general first, specific overrides).
    # Honest failure if no file exists at all.
    layers = [load(p) for p in candidates if os.path.exists(profiles_dir / p)]
    if not layers:
        return ProfileErrors([f"no profile found for {business_identity}. Looked at: {candidates}"])
    
    merged = deep_merge_in_order(layers)
    merged["resolution_path"] = [str(p) for p in candidates if os.path.exists(profiles_dir / p)]
    return merged
```

`deep_merge_in_order` is exactly what the V1 Postman JS does for corridor parameters today (it merges general + specific keys when both exist) — preserved as a documented helper instead of a one-off inline. No silent default-to-textile.

---

## 5. Backwards compatibility — the India-US-tex byte-equality guarantee

**Acceptance test:** given the V1 demo prompt (the one in `entAgentProject21/DATA/demo-prompts.md`) and the V1 sample loan document (`entAgentProject21/DATA/sample-loan-agreement.txt`), V2 must produce:

- the same `sofr_path` (8 quarterly points, identical to 4 decimal places),
- the same `swap_now_fixed_rate`, `swap_later_fixed_rate`,
- the same `A_total`, `B_total`, `C_total` from the ACTUS engine.

This is achieved by writing one profile file — `config/risk-factor-profiles/export-import/india-us-textiles.json` — that contains the V1 constants verbatim and declares the V1 components in the V1 order with V1 calibration coefficients. See `design-v1-config-architecture.md` §3 for that file's full content.

This test must run green before any other V2 feature is signed off. It is the regression gate.

---

## 6. The DRAPS contract — the one open item

**OPEN.** The DRAPS server today (per `entAgentProject21/backend/draps_client.py`, verified) accepts the V1 10-PRIMARY-input shape:

```
POST {DRAPS_URL}/api/simulate
{
  configData: {
    config_metadata: {config_id, collection_file: "SWAPS-1LOAN-WHAT-IF-DEMO.json"},
    exporter_country, importer_country, commodity_code,
    tariff_current, tariff_peak,
    loan_notional, loan_start_date, loan_maturity_date,
    swap_now_offset_months, swap_later_offset_months
  }
}
```

V2's composer produces a **fully resolved** payload — the SOFR path, the fixed rates, the loan dates — and what V2 wants is to hand all of that to DRAPS without DRAPS re-running its own derivation. Three resolutions are possible; choose one before coding:

**Option 1 — Extend the DRAPS contract.** Add an alternate endpoint or alternate `configData` shape that accepts `sofr_path[]`, `swap_now_fixed`, `swap_later_fixed`, `loan_fields` directly. The DRAPS JavaScript pre-request engine becomes the no-op for V2 calls. Requires a DRAPS change in `generalRisk/Backend/src/`. Cleanest, but adds a DRAPS commit.

**Option 2 — Move the deterministic JS into V2's Python.** Replicate the Postman JS derivation (which IS the V1 component formula) in Python under the Composer (N3d). Then call DRAPS only for the **ACTUS POST**, bypassing DRAPS's `/api/simulate` and going directly to `:8083/eventsBatch`. This is closer to what `entAgentProject21/backend/draps_client.py` already does for the V1 case (it builds the configData and POSTs). The V2 Composer would build the ACTUS PAM+SWAPS contracts itself. Cleanest separation — DRAPS becomes optional, V2 self-contained.

**Option 3 — Use the V1 path for backward-compat profiles, a new path for V2-only profiles.** A profile flag `dispatch: "draps_v1" | "v2_direct"` selects. India-US-tex stays on `draps_v1`; new profiles go to `v2_direct`. Hybrid; preserves V1 byte-equality automatically.

**Recommended choice:** Option 3 for the first cut (preserves V1 byte-equality with zero new failure modes), with Option 2 as the target for the second cut (cleaner long-term, less surface area). Option 1 is rejected — it's an external dependency change that V2 should not require.

**Validation needed before coding:** read `generalRisk/Backend/src/routes/simulation.routes.ts` (cited by `draps_client.py` as the source of truth for the DRAPS endpoint) to confirm the current contract. Decision left to that reading.

---

## 7. Invariants — what V2 preserves, what V2 adds

| Invariant | Status |
|---|---|
| **I1** prompt never reaches N4 | preserved (same grep test, now includes N3d) |
| **I2** validated_inputs has one producer, one consumer | preserved (now: knot_payload has one producer N3d, one consumer N4) |
| **I3** every node appends to audit_log | preserved + new entries from N3a/b/c/d/6a |
| **I4** retry edge bounded | preserved + new N3c→NX edge is non-retried by design (see §1 e10 note) |
| **I5** honest failure | preserved — Profile-Resolver fails honestly if profile absent, never substitutes |
| **I6** profile boundary (NEW) | only N3a / N3b read `config/risk-factor-profiles/` and `config/hedge-specs/` |
| **I7** provenance (NEW) | every numeric knot input has an attributable source in audit_log; N6a verifies at run-time |

---

## 8. What to verify before any code is written (V2 carry-forward)

Carrying forward from V1's §6 + new V2 items:

| # | Item | Where to confirm |
|---|---|---|
| 1 | DRAPS today supports only the 10-PRIMARY shape | read `generalRisk/Backend/src/routes/simulation.routes.ts` |
| 2 | The Postman JS derivation matches the V1 byte output | run the existing V1 demo, capture SOFR path, A/B/C; this becomes the regression fixture |
| 3 | ACTUS-Mentor `/generate-xbrl-report` accepts the V2 payload shape | confirm `events` field unchanged (V2 generates same events because knot unchanged) |
| 4 | Free APIs proposed in `design-v1-free-apis.md` actually return what V2 needs in the format claimed | one curl-per-API smoke test before binding any profile to a live source |
| 5 | The byte-equality regression for India-US-tex | full V1 prompt → V2 → identical A/B/C to V1 |

Items 1, 2, 5 are gating. Items 3, 4 are confirmatory.

---

## Bottom line

V2 is V1 + a configurable profile layer + a clean separation between risk-factor modelling and hedge parameterisation. The bow-tie is preserved exactly. The knot is unchanged at the agent level (with one open contract decision). The byte-equality regression on the working India-US-tex case is the gate.

**End of design-v1-detailed-design.md**
