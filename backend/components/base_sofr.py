"""
components/base_sofr.py — formula_id: base_sofr_fed_path_linear

Verbatim port of V1 `calcBaseSofr(monthOffset)` from the Postman pre-request
script in DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json.

V1 source (for audit):
    function calcBaseSofr(monthOffset) {
      const total_months = 24;
      if (monthOffset <= FED_PATH.months_to_peak) {
        return interpolate(FED_PATH.initial, FED_PATH.peak, monthOffset / FED_PATH.months_to_peak);
      } else {
        const remaining = total_months - FED_PATH.months_to_peak;
        return interpolate(FED_PATH.peak, FED_PATH.final, (monthOffset - FED_PATH.months_to_peak) / remaining);
      }
    }

In V1 `total_months = 24` is hardcoded inside the function and FED_PATH is a
const. In V2 every value comes from the PROFILE `components[base_sofr].inputs`
block (this is the byte-equality mechanism: numbers live in config, not code):
    inputs.initial, inputs.peak, inputs.final,
    inputs.months_to_peak, inputs.total_months_assumption

Returns a RATE FRACTION (e.g. 0.0450). No rounding (see _common.py).
"""

from __future__ import annotations

from ._common import interpolate


def base_sofr_fed_path_linear(inputs: dict, calibration: dict | None, t: float) -> float:
    """Fed forward-curve base SOFR at month offset `t`.

    `calibration` is unused for this component (accepted for the uniform
    COMPONENT_REGISTRY call signature `fn(inputs, calibration, t)` per
    design-v1-config-architecture.md §3 / detailed-design §3 N3d).
    """
    initial = inputs["initial"]
    peak = inputs["peak"]
    final = inputs["final"]
    months_to_peak = inputs["months_to_peak"]
    total_months = inputs["total_months_assumption"]

    if t <= months_to_peak:
        return interpolate(initial, peak, t / months_to_peak)

    remaining = total_months - months_to_peak
    return interpolate(peak, final, (t - months_to_peak) / remaining)
