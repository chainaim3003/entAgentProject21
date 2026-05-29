"""
components/inventory_carrying.py — formula_id: inventory_carrying_dso_dpo

NEW in Iteration 7 (DESIGN-V1 derived_domestic mode, ecommerce audience). No V1
precedent. Sibling of `payment_cycle.py` / `wc.py` — same trapezoid machinery
(ramp → plateau → descent), different driver.

Per design-v1-risk-factor-catalog.md §b.2:
    "Maps to component: inventory_carrying_dso_dpo (proposed). Formula combines
     current ISR vs historic mean with sector-DIO sensitivity to produce a
     working-capital stress bp."
and the catalog's ISR reference points (§b.2):
    "FRED ISRATIO — Retailers' Inventory-to-Sales Ratio (key signal — historic
     ~1.45; >1.6 = gluts, <1.3 = stockouts)."

The catalog lists `inventory_carrying_dso_dpo` as a CORE component for the
"Ecommerce" column of the audience matrix (catalog §"Component-to-audience
matrix") — that is why Iter-7 lands it for us-ecommerce.json. NOTE the matrix
also keeps `payment_cycle_stress_dso` as "yes" for ecommerce; inventory_carrying
ADDS to the domestic skeleton rather than replacing payment_cycle.

────────────────────────────────────────────────────────────────────────────
CLOSED-FORM CHOICE — ITER-7, *** PENDING USER SIGN-OFF ***
────────────────────────────────────────────────────────────────────────────
The catalog gives intent ("combines ISR-vs-mean with sector-DIO sensitivity")
but no closed-form curve over t (month offset). Following the precedent of the
Iter-6 siblings (demand_volatility / payment_cycle, whose closed forms were
"signed off by user"), this file pins a concrete form that mirrors
`payment_cycle_stress_dso`:

  1. ISR deviation is taken as ABSOLUTE: both gluts (ISR > mean → excess
     carrying cost) and stockouts (ISR < mean → lost-sales / expediting cost)
     widen working-capital financing cost per the catalog ("Both affect working
     capital"). This matches demand_volatility's abs(pmi_gap) convention, NOT
     payment_cycle's one-sided max(0, ...).
  2. The peak stress is derived inside the formula:
         peak_bps = baseline_bps + isr_deviation
                                    * sensitivity_bps_per_ratio_point
                                    * dio_sensitivity
     where `dio_sensitivity` is the catalog's explicit "sector-DIO sensitivity"
     dimensionless multiplier (a high-DIO sector finances inventory longer, so
     the same ISR swing costs it more).
  3. The stress then follows the shared trapezoid (ramp → plateau → descent)
     keyed off inputs.stress_timing, identical to payment_cycle / wc.

This combination is multiplicative and is an Iter-7 modelling decision, not a
catalog mandate. If the user prefers (a) folding dio_sensitivity into
sensitivity_bps_per_ratio_point, (b) a one-sided glut-only excess, or (c) a
DSO/DPO cash-conversion-cycle term to honour the `_dso_dpo` suffix literally,
this is the single place to change it. Until signed off, treat the 9-point
numeric vector this produces as ILLUSTRATIVE (see us-ecommerce.json _notes).

V2 input mapping (PROFILE components[inventory_carrying].inputs):
  inputs.isr_observed                   (current inventory-to-sales ratio; e.g. 1.62)
  inputs.isr_historic_mean              (long-run ISR mean; FRED ~1.45)
  inputs.sensitivity_bps_per_ratio_point(bp peak-add per 1.0 of |ISR - mean|)
  inputs.dio_sensitivity                (dimensionless sector-DIO multiplier; >0)
  inputs.baseline_bps                   (baseline carrying stress, bps)
  inputs.stress_timing.{months_to_peak, plateau_months, descent_months}

UNITS: returns a RATE FRACTION (e.g. 0.0008 == 8bps). No rounding here; the
Composer sums component fractions and rounds once per SOFR-path point. See
_common.py for the convention.
"""

from __future__ import annotations

from ._common import trapezoid


def inventory_carrying_dso_dpo(
    inputs: dict,
    calibration: dict | None,
    t: float,
) -> float:
    """Inventory-carrying / supply-demand-mismatch stress at month offset `t`.

    `calibration` is unused (accepted for the uniform COMPONENT_REGISTRY
    signature `fn(inputs, calibration, t)` per design-v1-config-architecture.md
    §3 / detailed-design §3 N3d).
    """
    isr_observed = inputs["isr_observed"]
    isr_historic_mean = inputs["isr_historic_mean"]
    sensitivity_bps_per_ratio_point = inputs["sensitivity_bps_per_ratio_point"]
    dio_sensitivity = inputs["dio_sensitivity"]
    baseline_bps = inputs["baseline_bps"]

    isr_deviation = abs(isr_observed - isr_historic_mean)
    peak_bps = baseline_bps + isr_deviation * sensitivity_bps_per_ratio_point * dio_sensitivity

    initial = baseline_bps / 10000.0
    peak = peak_bps / 10000.0

    return trapezoid(initial, peak, inputs["stress_timing"], t)
