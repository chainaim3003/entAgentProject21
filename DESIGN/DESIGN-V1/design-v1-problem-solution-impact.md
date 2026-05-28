# hedgeAdvisor2 — design-v1-problem-solution-impact

## 1. What V1 solved, and where it stops

**VERIFIED from `entAgentProject21/DESIGN/DESIGN1/design-1-problem-solution-impact.md`:** V1 frames a US manufacturer with a floating-rate working-capital loan financing **import-dependent supply chains**. The stochastic forces it models are **tariff escalation on imported inputs** and **central-bank rate moves**. The hedge instrument is a USD interest-rate swap.

**VERIFIED from `generalRisk/Backend/config/simulation/local/supplychain-tariff/supply-chain-tariff-4/SWAPS-1LOAN-WHAT-IF-3-INP-FINAL.json`:** the production scenario is hard-wired to:

| Dimension | V1 hard-wired value |
|---|---|
| Exporter country | India |
| Importer country | United States |
| Commodity codes | `tex`, `pha`, `oil` only |
| Armington elasticities | 3.8 / 2.4 / 8.9 (from `GTAP_COMMODITIES` table inline in the Postman pre-request JS) |
| Sovereign stress | India BBB, 50bps→70bps under tariff stress |
| Working-capital stress | DSO 60→90 days, 30bps→50bps |
| Tariff pass-through | 20% baseline, with commodity-specific overrides (textiles 20%, pharma 15%, oil 30%) |
| Loan spread | 250bps IG baseline, commodity-specific overrides |
| SOFR Fed path | 4.50% → 5.50% (peak month 12) → 4.75% (final), linear interpolation |
| Calibration polynomial | quadratic: constant −35.9048, linear 133.6627, quadratic −116.1008 |
| Swap discounts | swap-now 100bps below SOFR, swap-later 70bps below SOFR |

The Postman JS sums four additive components per quarter to produce the SOFR path:
`total_sofr(t) = base_sofr(t) + tariff_component(t) + sovereign(t) + wc(t)`
where `tariff_component(t) = (tariff(t) × armington × pass_through) × calibration_polynomial(tariff(t))`. The ACTUS engine then runs three deterministic simulations against this SOFR path — Scenario A (no swap), B (swap at month 0, fixed = sofr_at_month_0 − 100bps), C (swap at month 3, fixed = sofr_at_month_3 − 70bps).

**Where it stops:** every assumption above lives in one file. Asking V1 to handle a US-domestic ecommerce business is not a config change — it is a rewrite, because the inputs the JS reads (`exporter_country`, `tariff_current`, `armington_elasticity`) are not optional and have no meaning for a domestic business.

---

## 2. The three new problems V2 must solve

These are the user's exact three asks, restated as design problems.

### Problem A — Allow SOFR rates to be supplied (skip the risk-factor model)

A caller — a sophisticated treasurer, an external pricing engine, a bank's own swap desk — already has SOFR curve points and the fixed rates the swap desk is quoting. They want to feed those in and get the A/B/C totals back. They do **not** want V2 to second-guess their numbers with a GTAP derivation.

**What this means architecturally:** the SOFR path and the swap fixed rates become a possible *input*, not always an *output*. The risk-factor wing becomes skippable. The deterministic knot stays unchanged — it just receives the path from a different producer.

### Problem B — Allow SOFR rates to be derived for any commodity / any corridor, including the existing India-US textile case

The V1 GTAP_COMMODITIES table has three entries. The V1 CORRIDOR_PARAMETERS table has one base corridor (India-US) with three commodity overrides. To work "for any commodity and any corridor" the table needs to be (i) externalised from JS to JSON, (ii) extensible by config files dropped on disk, (iii) backed by primary-source data where possible. **And** the existing India-US-tex case must produce **byte-identical SOFR path and A/B/C totals** to V1 — that is the regression test V2 must pass before being declared working.

**What this means architecturally:** a `Risk-Factor-Profile-Resolver` agent on the left wing, deterministic, reads externalised config files (commodity profile, corridor profile, sovereign profile, working-capital profile) and produces the same four-component SOFR path V1 produced from inline JS. For the India-US-tex case the resolver reads files that contain the V1 numbers verbatim. For new commodity/corridor combinations it reads new files — or fails honestly when a needed file is absent. **No silent default-to-textile.**

### Problem C — Allow non export/import businesses (domestic US, ecommerce, services)

A US-domestic ecommerce business with a floating-rate working-capital loan has no tariff exposure, no sovereign-rating spread (it's USD-on-USD), and no GTAP commodity. It does have other risk factors: supply/demand mismatch on inventory, port congestion if any of its goods are imported finished, payment-cycle stress (late payments from B2B customers), domestic regulatory cost shocks. These factors still move forward SOFR expectations and the bank's credit spread on the loan, but **through different channels** than tariff pass-through.

**What this means architecturally:** the SOFR-component model must be **pluggable** at the component level — a profile chooses which components apply, and each component is a function `(state, t) → bps`. Components for export-import (`tariff`, `sovereign`, `wc`) are one set. Components for domestic ecommerce (`demand_volatility`, `inventory_carrying_stress`, `payment_cycle_stress`, `wc`) are another set. The four-component additive structure from V1 is generalised to an **N-component additive structure** where N and the set of components depend on the profile.

---

## 3. Solution — the new bow-tie

Two new agents on the left wing, one new sub-boundary, no change to the knot, one new agent on the right wing.

### Left wing additions

**Risk-Factor-Profile-Resolver Agent** — *deterministic*. Given the validated business identity (industry, corridor, commodity, jurisdiction), it loads the matching risk-factor profile config(s) from `config/risk-factor-profiles/` and produces a structured `risk_factor_profile` object: which SOFR components apply, what each component's inputs are, where each input came from (file path, API call, or supplied-by-caller). If a required profile is missing, it produces a `risk_factor_errors` list — never a silent default.

**Hedge-Spec-Resolver Agent** — *deterministic*. Given the loan + the user's hedge intent, it loads the matching hedge-spec config from `config/hedge-specs/` and produces a `hedge_spec` object: which swap structures to simulate (A/B/C is the default but configurable), what offsets, what fixed-rate computation rule (discount-from-SOFR-by-Nbps, or supplied, or market-quoted). Same honest-failure pattern.

**Risk-Factor-Composer Agent** — *deterministic*. Given the resolved profile, composes the SOFR path the knot will receive. Three modes:
- **`supplied`** — the caller already provided `sofr_path` + `swap_now_fixed_rate` + `swap_later_fixed_rate`. Composer passes them through with provenance-stamping (so the audit log can prove the knot's input came from outside, not from V2's models). This is **Problem A**.
- **`derived`** — composer runs the additive component formula from the resolved profile. For the India-US-tex profile this reproduces V1's four-component formula and V1's quadratic calibration. For new profiles it runs whatever components the profile declares. This is **Problem B**.
- **`derived_domestic`** — same machinery, different component set: no tariff, no sovereign, instead demand/inventory/payment components. This is **Problem C**.

The mode is chosen by the profile, not by code. Adding a new mode is adding a new profile, not editing the composer.

### Wing boundary additions

**Profile-and-Spec-Validator Agent** — *deterministic*. The Input-Validator from V1 stays unchanged for the loan-level schema check. The new validator sits next to it on the left wing and schema-checks the resolved profile + resolved hedge-spec. Same architectural role as the V1 Input-Validator: nothing schema-dirty crosses into the composer or the knot.

### The knot is unchanged

**Simulation Agent** — *deterministic*, still wraps DRAPS `run_simulation`, still reads only the validated payload. What changes is the *contents* of that payload: it now carries an explicit `sofr_path` and `swap_now_fixed_rate` / `swap_later_fixed_rate` rather than the 10 PRIMARY variables. See `design-v1-detailed-design.md` §6 for the contract question — **OPEN whether DRAPS today accepts SOFR-path-as-input or must be extended**.

### Right wing addition

**Provenance Agent** — *deterministic*, off-critical-path. Walks the audit log and produces a one-page provenance report: every number in the A/B/C totals traces to either (i) a config file on disk with checksum, (ii) a free-API call with timestamp + response hash, or (iii) a caller-supplied input flagged as such. This is the audit trail Problem A makes essential — "the customer supplied 5.20% as the swap-now rate, here is when and through which endpoint."

---

## 4. Impact

### For the existing India-US-tex exporter (the V1 customer)

Nothing changes operationally. The same prompt + the same loan document produces the same SOFR path and the same A/B/C totals — that is the regression test gate. What they gain is **a clean way to override** any single assumption: a treasurer who disagrees with the 20% pass-through can drop a one-line override file and re-run, without forking the GTAP table.

### For a new corridor (e.g. Vietnam→US apparel, Mexico→US auto parts)

The user creates one corridor profile + one commodity profile (or reuses GTAP elasticity from the existing source), confirms the resulting parameters with a desk-check, and runs. Hours, not a code change.

### For a US-domestic ecommerce business

A new industry profile (`domestic-ecommerce-us.json`) declares the component set (`demand_volatility`, `inventory_carrying`, `payment_cycle`, `wc`). Each component points at a free-API source (NY Fed GSCPI for supply-chain pressure, FRED for SOFR base, BLS for sector-level wage/PPI) and a transformation function. Once the profile is written, every ecommerce business in the same industry vertical reuses it.

### For a US-domestic services business (SaaS, consulting)

Even simpler — inventory and tariff components don't apply at all. The profile reduces to (`demand_volatility`, `payment_cycle`, `wc`). The same hedge analysis applies: should a SaaS company with a floating-rate revolving credit facility lock the rate now, in 3 months, or stay floating? The math is the math; the inputs are domestic-services inputs.

### For Japan and India based businesses (the user's expand-from-US ask)

The components and the composer don't care about country. What changes is the **profile** — Japan-business profile uses JGB curve as the rate base, BoJ policy path, Japan-specific port congestion (Yokohama, Tokyo), JPY working-capital metrics from BoJ Tankan; India-business profile uses MIBOR/MCLR as rate base, RBI policy, India port data (Mumbai, Chennai), INR working-capital from RBI sectoral surveys. The same agent architecture handles all three (US / Japan / India) — only the profile files differ. See `design-v1-free-apis.md` for the API source lists for each country.

---

## 5. What did NOT change from V1

This is the conservation list — every item below is preserved byte-for-byte from `entAgentProject21`:

- The bow-tie agent-type law (reasoning on wings, deterministic at knot).
- The 8-agent roster (N0–N8) — V2 adds agents, does not remove any.
- The invariants I1 (prompt boundary), I2 (clean-inputs gate), I3 (audit log), I4 (bounded retry), I5 (honest failure).
- The DRAPS knot — same deterministic simulation, same A/B/C contract types (PAM loan + SWAPS).
- The ACTUS-Mentor disclosure path.
- The LangGraph checkpointer / resume semantics.
- The FastAPI + Vite frontend skeleton.

V2 is **strictly additive** at the architectural level. The new agents extend the wings; nothing in the knot is touched.

---

## 6. What V2 explicitly does NOT do

- **No live tariff feed.** Tariff inputs come from the corridor profile (or are supplied). A live tariff-API agent is a Phase 3 addition — see `design-v1-free-apis.md` §6 for candidate sources (USTR, USITC HTS, WITS UNCTAD-TRAINS).
- **No automated profile generation.** Profile files are authored by humans (or by an offline tool that snapshots a verified source). The runtime never invents a profile.
- **No replacement of GTAP.** Where Armington elasticities are used, they come from the GTAP database (cited per commodity in the commodity profile file). Where Armington does not apply (domestic businesses, services), the profile says so explicitly — it does not fake an elasticity.

---

**End of design-v1-problem-solution-impact.md**
