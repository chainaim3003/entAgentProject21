"""
components/demand_volatility.py — formula_id: demand_volatility_vix_proxy

NEW in Iteration 6 (DESIGN-V1 derived_domestic mode). No V1 precedent —
V1's Postman JS does not derive a demand-volatility component. The formula
shape here implements design-v1-risk-factor-catalog.md §b.1's "Formula sketch":

    "convert a sector-PMI delta from neutral to a credit-spread bp adjustment
     with a profile-configurable sensitivity."

The catalog gives intent but no closed-form curve over t (month offset).
Iter-6 design choice (signed off by user): model the shock as a LINEAR DECAY
from the current PMI-implied shock toward a long-run baseline over
`decay_months`, then flat at baseline. This matches the "VIX proxy" semantics
(vol shocks mean-revert) and reuses the existing `_common.interpolate` helper
used by `base_sofr.py`.

PMI deviation is taken as ABSOLUTE: either contraction (PMI < neutral) or
overheating (PMI > neutral) widens working-capital financing cost in the
catalog's framing. A profile that wants asymmetric behaviour can supply a
clamped `pmi_current` upstream.

V2 input mapping (PROFILE components[demand_volatility].inputs):
  inputs.pmi_neutral               (e.g. 50.0)
  inputs.pmi_current               (current PMI reading)
  inputs.sensitivity_bps_per_point (bp peak-add per 1-point PMI deviation)
  inputs.baseline_bps              (long-run baseline vol premium, bps)
  inputs.decay_months              (months for shock to fade to baseline; >0)

UNITS: returns a RATE FRACTION (e.g. 0.0008 == 8bps). No rounding here; the
Composer rounds once per SOFR-path point. See _common.py for the convention.
"""

from __future__ import annotations

from ._common import interpolate


def demand_volatility_vix_proxy(
    inputs: dict,
    calibration: dict | None,
    t: float,
) -> float:
    """Demand-volatility credit-spread shock at month offset `t`.

    `calibration` is unused (accepted for the uniform COMPONENT_REGISTRY
    signature `fn(inputs, calibration, t)` per design-v1-config-architecture.md
    §3 / detailed-design §3 N3d).
    """
    pmi_neutral = inputs["pmi_neutral"]
    pmi_current = inputs["pmi_current"]
    sensitivity_bps_per_point = inputs["sensitivity_bps_per_point"]
    baseline_bps = inputs["baseline_bps"]
    decay_months = inputs["decay_months"]

    pmi_gap = abs(pmi_neutral - pmi_current)
    initial_bps = baseline_bps + pmi_gap * sensitivity_bps_per_point

    if t <= decay_months:
        bps_at_t = interpolate(initial_bps, baseline_bps, t / decay_months)
    else:
        bps_at_t = baseline_bps

    return bps_at_t / 10000.0
