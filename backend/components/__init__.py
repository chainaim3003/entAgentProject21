"""
components — the COMPONENT_REGISTRY for V2's v2_direct SOFR derivation (6a).

Maps each profile `formula_id` to its Python formula function. Every function
is a verbatim port of the matching V1 Postman JS (DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json)
and shares the uniform call signature used by the Composer's derived branch
(design-v1-config-architecture.md §3 / detailed-design §3 N3d):

    fn(inputs: dict, calibration: dict | None, t: float) -> float   # rate FRACTION

where `t` is the month offset (0, 3, 6, ... in the V1 quarterly tenor grid).

UNITS: every function returns a RATE FRACTION and does NO rounding. The
Composer sums the four fractions and rounds once (.4f) per SOFR-path point.
See _common.py for the conflict note vs design §3's `value_bps` framing.

The registry keys are the profile `formula_id` strings; N3c already enforces
that every profile formula_id resolves to a component (cross-file check,
design-v1-config-architecture.md §6).
"""

from __future__ import annotations

from typing import Callable

from .base_sofr import base_sofr_fed_path_linear
from .tariff import tariff_gtap_quadratic
from .sovereign import sovereign_trapezoidal
from .wc import wc_trapezoidal
from .demand_volatility import demand_volatility_vix_proxy
from .payment_cycle import payment_cycle_stress_dso
from .inventory_carrying import inventory_carrying_dso_dpo

# formula_id -> formula function
COMPONENT_REGISTRY: dict[str, Callable[[dict, "dict | None", float], float]] = {
    "base_sofr_fed_path_linear": base_sofr_fed_path_linear,
    "tariff_gtap_quadratic": tariff_gtap_quadratic,
    "sovereign_trapezoidal": sovereign_trapezoidal,
    "wc_trapezoidal": wc_trapezoidal,
    "demand_volatility_vix_proxy": demand_volatility_vix_proxy,
    "payment_cycle_stress_dso": payment_cycle_stress_dso,
    "inventory_carrying_dso_dpo": inventory_carrying_dso_dpo,
}

__all__ = [
    "COMPONENT_REGISTRY",
    "base_sofr_fed_path_linear",
    "tariff_gtap_quadratic",
    "sovereign_trapezoidal",
    "wc_trapezoidal",
    "demand_volatility_vix_proxy",
    "payment_cycle_stress_dso",
    "inventory_carrying_dso_dpo",
]
