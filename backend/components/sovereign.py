"""
components/sovereign.py — formula_id: sovereign_trapezoidal

Verbatim port of V1 `calcSovereign(monthOffset)` from the Postman pre-request
script in DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json.

V1 source (for audit):
    function calcSovereign(monthOffset) {
      const peak = STRESS_TIMING.months_to_peak;
      const plateau = STRESS_TIMING.plateau_months;
      const descent = STRESS_TIMING.descent_months;
      if (monthOffset <= peak) {
        return interpolate(corridor.sovereign_initial, corridor.sovereign_peak, monthOffset / peak);
      } else if (monthOffset <= peak + plateau) {
        return corridor.sovereign_peak;
      } else {
        const progress = (monthOffset - peak - plateau) / descent;
        return interpolate(corridor.sovereign_peak, corridor.sovereign_initial, progress);
      }
    }

The body is identical to calcWC (only the initial/peak inputs differ), so the
math lives once in _common.trapezoid to prevent the two from silently drifting.

V2 input mapping (PROFILE components[sovereign]):
  inputs.initial -> V1 corridor.sovereign_initial (0.0050)
  inputs.peak    -> V1 corridor.sovereign_peak    (0.0070)
  inputs.stress_timing.{months_to_peak, plateau_months, descent_months} (12/3/9)

Returns a RATE FRACTION. No rounding.
"""

from __future__ import annotations

from ._common import trapezoid


def sovereign_trapezoidal(inputs: dict, calibration: dict | None, t: float) -> float:
    """Sovereign credit-spread stress at month offset `t`.

    `calibration` is unused (accepted for the uniform registry signature).
    """
    return trapezoid(inputs["initial"], inputs["peak"], inputs["stress_timing"], t)
