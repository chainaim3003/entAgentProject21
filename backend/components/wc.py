"""
components/wc.py — formula_id: wc_trapezoidal

Verbatim port of V1 `calcWC(monthOffset)` from the Postman pre-request script
in DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json.

V1 source (for audit):
    function calcWC(monthOffset) {
      const peak = STRESS_TIMING.months_to_peak;
      const plateau = STRESS_TIMING.plateau_months;
      const descent = STRESS_TIMING.descent_months;
      if (monthOffset <= peak) {
        return interpolate(corridor.wc_initial, corridor.wc_peak, monthOffset / peak);
      } else if (monthOffset <= peak + plateau) {
        return corridor.wc_peak;
      } else {
        const progress = (monthOffset - peak - plateau) / descent;
        return interpolate(corridor.wc_peak, corridor.wc_initial, progress);
      }
    }

Same trapezoid as calcSovereign (shared body in _common.trapezoid), different
inputs.

V2 input mapping (PROFILE components[wc]):
  inputs.initial -> V1 corridor.wc_initial (0.0030)
  inputs.peak    -> V1 corridor.wc_peak    (0.0050)
  inputs.stress_timing.{months_to_peak, plateau_months, descent_months} (12/3/9)

Returns a RATE FRACTION. No rounding.
"""

from __future__ import annotations

from ._common import trapezoid


def wc_trapezoidal(inputs: dict, calibration: dict | None, t: float) -> float:
    """Working-capital stress at month offset `t`.

    `calibration` is unused (accepted for the uniform registry signature).
    """
    return trapezoid(inputs["initial"], inputs["peak"], inputs["stress_timing"], t)
