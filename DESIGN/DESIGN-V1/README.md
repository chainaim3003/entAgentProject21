# hedgeAdvisor2 — DESIGN-V1

This is the **first version** of the redesign that generalizes the existing ACTUS Hedge Advisor (in `entAgentProject21`) so it can serve **any business in any corridor with any commodity**, while preserving the working India→US textile/pharma/oil exporter scenario.

---

## Why a new design

The V1 (predecessor, in `entAgentProject21`) is hard-wired to a single problem shape: a US-importer / India-exporter loan exposed to a small fixed set of commodity tariffs. The risk-factor model (GTAP Armington elasticity × tariff pass-through × sovereign + WC stresses) and the hedge parameters (swap_now / swap_later offsets, fixed-rate computation) live entangled in one Postman collection JSON (`SWAPS-1LOAN-WHAT-IF-3-INP-FINAL.json`, 36 KB, in `generalRisk/Backend/config/simulation/local/supplychain-tariff/supply-chain-tariff-4/`).

The user has now asked for three things, each of which breaks the entangled shape:

- **A.** Allow SOFR rates for the A/B/C scenarios to be **supplied directly** by the caller (skip the risk-factor derivation entirely).
- **B.** Allow SOFR rates to be **derived for any commodity and any corridor**, using GTAP/Armington and supply-chain factors beyond what the current JSON encodes — while keeping the India-US textile case working byte-for-byte identical.
- **C.** Allow the same machinery to serve **non export/import businesses** (domestic US, e-commerce, services) where tariff/sovereign risk does not apply but other risk factors do.

The first principle of the redesign: **risk-factor modelling and hedge parameters become two separate config dimensions**, each with its own schema and its own pluggable provider. That separation is what makes A, B, and C possible without forking the codebase.

---

## Files in this folder

| File | Contents |
|---|---|
| `design-v1-problem-solution-impact.md` | The reframed problem, the generalised solution, the impact across the three new audiences (export-import, ecommerce, services). What changed from V1. |
| `design-v1-conceptual-design.md` | The bow-tie diagram updated for V2 — same agent-type law, two new wing agents (Risk-Factor-Profile and Hedge-Spec), one new boundary (Risk-Factor-Validator), no change to the knot. |
| `design-v1-detailed-design.md` | Node-by-node textual graph, state schema diff vs V1, invariants preserved + new ones, conditional routing for the three modes (supplied / derived / domestic). |
| `design-v1-config-architecture.md` | The core of the change. How **one** monolithic JSON becomes **N** small, composable JSONs (industry profile + corridor profile + commodity profile + hedge spec + SOFR override). Schema for each. How resolution / fallback works. Why this does not break the working India-textile case. |
| `design-v1-risk-factor-catalog.md` | Catalog of risk factors organised by business type: (a) export-import, (b) ecommerce / supply-demand, (c) domestic small-business. For each: definition, data source, how it maps into the SOFR-path components used by the deterministic knot. |
| `design-v1-free-apis.md` | Free / open-data APIs that can populate risk factors. Source quality, license, rate limits, what they cover for the three audiences, and Japan-and-India coverage notes. |
| `design-v1-migration-plan.md` | How to roll this out without breaking the working V1: directory layout, fallback rules, what code is reused unchanged from `entAgentProject21`, what changes, what is genuinely new. Tests required before declaring V2 working. |
| `design-v1-project-structure.md` | File-by-file layout of the V2 codebase, mirroring the V1 layout where possible. |

---

## Status of this design

- **VERIFIED** items are facts read directly from disk or from cited primary sources. The relevant file path or URL is given inline.
- **PROPOSED** items are new design choices in V2 that have not been built yet.
- **OPEN** items are questions that need a decision before code is written.

Following the V1 discipline: **no mocks, no hardcoding, no fallbacks that fabricate results**. Every config file is real or absent — there is no "default to India-textile" silent fallback.

---

## What is NOT in this design (and why)

- **No new ACTUS contract types.** PAM + SWAPS (already used in V1) cover all three new audiences. The knot does not grow — that is the architectural law from V1.
- **No new LLM agents at the knot.** Reasoning agents stay on the wings.
- **No replacement of DRAPS.** DRAPS is still the deterministic knot. What changes is the **inputs** DRAPS receives, not DRAPS itself. If DRAPS today only accepts the 10 PRIMARY variables defined in `SWAPS-1LOAN-WHAT-IF-3-INP-FINAL.json`, V2 must either (i) extend the DRAPS contract or (ii) precompute the SOFR path on the V2 side and pass it in. See `design-v1-detailed-design.md` §6 — this is the single open contract risk for V2.

---

**Author:** Claude (Opus 4.7), 2026-05-23
**Source codebase read:** `entAgentProject21/` (commit unspecified) + `generalRisk/Backend/config/simulation/local/supplychain-tariff/supply-chain-tariff-4/SWAPS-1LOAN-WHAT-IF-3-INP-FINAL.json`
