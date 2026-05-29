"""
components/payment_cycle.py — formula_id: payment_cycle_stress_dso

NEW in Iteration 6 (DESIGN-V1 derived_domestic mode). No V1 precedent.
Sibling of `wc_trapezoidal` — same trapezoid machinery, different driver.

Per design-v1-risk-factor-catalog.md §b.5:
    "Formula: DSO above sector median → bp add to working-capital stress curve."

The catalog lists `payment_cycle_stress_dso` as the CORE component for
"Domestic services" in the audience matrix (catalog §"Component-to-audience
matrix") — that's why Iter-6 lands it for us-services.json.

Formula shape (signed off by user): same trapezoid as `wc.py`
(ramp → plateau → descent), but the PEAK is derived from DSO-excess ×
sensitivity inside the formula rather than supplied directly by the profile.
This makes the formula meaningful w.r.t. its `_stress_dso` naming rather
than being a wc rename. DSO_excess = max(0, observed - median), so a healthy
payer (observed <= median) sees only the baseline carry.

V2 input mapping (PROFILE components[payment_cycle].inputs):
  inputs.dso_observed              (days; e.g. 58)
  inputs.dso_median                (sector median DSO; e.g. 35)
  inputs.sensitivity_bps_per_day   (bp peak-add per day above median)
  inputs.baseline_bps              (baseline payment-cycle stress, bps)
  inputs.stress_timing.{months_to_peak, plateau_months, descent_months}

UNITS: returns a RATE FRACTION. No rounding here; Composer rounds once per
SOFR-path point. See _common.py for the convention.
"""

from __future__ import annotations

from ._common import trapezoid


def payment_cycle_stress_dso(
    inputs: dict,
    calibration: dict | None,
    t: float,
) -> float:
    """Payment-cycle stress (DSO-driven) at month offset `t`.

    `calibration` is unused (accepted for the uniform COMPONENT_REGISTRY
    signature `fn(inputs, calibration, t)`).
    """
    dso_observed = inputs["dso_observed"]
    dso_median = inputs["dso_median"]
    sensitivity_bps_per_day = inputs["sensitivity_bps_per_day"]
    baseline_bps = inputs["baseline_bps"]

    dso_excess = max(0.0, dso_observed - dso_median)
    peak_bps = baseline_bps + dso_excess * sensitivity_bps_per_day

    initial = baseline_bps / 10000.0
    peak = peak_bps / 10000.0

    return trapezoid(initial, peak, inputs["stress_timing"], t)
