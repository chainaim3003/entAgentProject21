"""
components/tariff.py — formula_id: tariff_gtap_quadratic

Verbatim port of V1 `calcTariffComponent(monthOffset)` from the Postman
pre-request script in DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json.

V1 source (for audit):
    function calcTariffComponent(monthOffset) {
      let tariff_rate;
      if (monthOffset <= STRESS_TIMING.months_to_peak) {
        tariff_rate = interpolate(PRIMARY.tariff_current, PRIMARY.tariff_peak, monthOffset / STRESS_TIMING.months_to_peak);
      } else {
        tariff_rate = PRIMARY.tariff_peak;
      }
      const gtap_base_bps = (tariff_rate * armington_elasticity * corridor.pass_through) * 100;
      const calibration_mult = CALIBRATION.constant + CALIBRATION.linear * tariff_rate + CALIBRATION.quadratic * (tariff_rate * tariff_rate);
      const tariff_bps = gtap_base_bps * calibration_mult;
      return tariff_bps / 10000;
    }

CRITICAL byte-equality details confirmed from source:
  - The quadratic calibration polynomial is evaluated on the TIME-VARYING
    `tariff_rate` (the ramped tariff at offset t), NOT on a static tariff.
  - Despite the name `gtap_base_bps`, the function returns a RATE FRACTION:
    the final `tariff_bps / 10000`. No rounding here.
  - Only `months_to_peak` from stress_timing is used (ramp then flat); the
    plateau/descent fields are not consulted for the tariff component.

V2 input mapping (PROFILE components[tariff]):
  inputs.tariff_current_pct  -> V1 PRIMARY.tariff_current  (0.50)
  inputs.tariff_peak_pct     -> V1 PRIMARY.tariff_peak     (0.60)
  inputs.armington_elasticity-> V1 armington_elasticity    (3.8, from GTAP lookup)
  inputs.pass_through        -> V1 corridor.pass_through   (0.20)
  inputs.stress_timing.months_to_peak -> V1 STRESS_TIMING.months_to_peak (12)
  calibration.coefficients.{constant,linear,quadratic} -> V1 CALIBRATION
                                  (-35.9048 / 133.6627 / -116.1008)

The calibration coefficients live in the PROFILE (not hardcoded) — that is the
byte-equality mechanism per design-v1-config-architecture.md §3.1.
"""

from __future__ import annotations

from ._common import interpolate


def tariff_gtap_quadratic(inputs: dict, calibration: dict, t: float) -> float:
    """GTAP-grounded tariff stress component at month offset `t`.

    Returns a RATE FRACTION. Raises KeyError honestly if a required input or
    calibration coefficient is absent (N3c validates shape before the Composer
    calls this; no silent defaults — per the project's no-silent-fallback law).
    """
    tariff_current = inputs["tariff_current_pct"]
    tariff_peak = inputs["tariff_peak_pct"]
    armington = inputs["armington_elasticity"]
    pass_through = inputs["pass_through"]
    months_to_peak = inputs["stress_timing"]["months_to_peak"]

    coeffs = calibration["coefficients"]
    c_constant = coeffs["constant"]
    c_linear = coeffs["linear"]
    c_quadratic = coeffs["quadratic"]

    if t <= months_to_peak:
        tariff_rate = interpolate(tariff_current, tariff_peak, t / months_to_peak)
    else:
        tariff_rate = tariff_peak

    gtap_base_bps = (tariff_rate * armington * pass_through) * 100
    calibration_mult = c_constant + c_linear * tariff_rate + c_quadratic * (tariff_rate * tariff_rate)
    tariff_bps = gtap_base_bps * calibration_mult

    return tariff_bps / 10000
