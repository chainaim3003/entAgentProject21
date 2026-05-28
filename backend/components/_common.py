"""
components/_common.py — shared primitives for the COMPONENT_REGISTRY formulas.

These are VERBATIM ports of the helper functions in the V1 derivation engine
(the Postman pre-request script in DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json, function
`interpolate` and the trapezoid bodies inside `calcSovereign` / `calcWC`).

UNITS CONVENTION (load-bearing for byte-equality)
--------------------------------------------------
Every component formula returns a RATE FRACTION (e.g. 0.0450 == 4.50%), NOT
basis points. The V1 engine sums the four component fractions raw:

    total = base + tariff + sovereign + wc

and rounds EXACTLY ONCE at the SOFR-path point:

    value = parseFloat(total.toFixed(4))

The component functions themselves perform NO rounding. The single round to 4
decimals is the Composer's job (deliverable 2), applied to the summed total.

NOTE — conflict with design-v1-config-architecture.md §3 (N3d pseudocode):
that pseudocode says `value_bps = fn(...)` then `value: total_bps/10000`. The
V1 JS uses the fraction convention above and produces the locked digest
(events_digest_sha256 = e5d26f1b...). The V1 JS is authoritative for the
byte-equality lock, so these ports use fractions. The Composer (deliverable 2)
MUST sum fractions and round once; it MUST NOT apply a further /10000.
"""

from __future__ import annotations


def interpolate(start: float, end: float, progress: float) -> float:
    """Linear interpolation. Verbatim port of V1 `interpolate(start, end, progress)`.

    progress is expected in [0, 1] for in-range interpolation, but is NOT
    clamped — the V1 engine never calls it out of range (the caller's branch
    guards keep monthOffset within each segment), and clamping here could mask
    a future tenor-grid bug rather than fail honestly.
    """
    return start + (end - start) * progress


def trapezoid(initial: float, peak: float, stress_timing: dict, t: float) -> float:
    """Ramp -> plateau -> descent trapezoid. Verbatim port of the body shared by
    V1 `calcSovereign(monthOffset)` and `calcWC(monthOffset)`.

    Segments (boundaries inclusive on the lower branch, matching the JS `<=`):
      t <= months_to_peak                      : ramp initial -> peak
      months_to_peak < t <= +plateau_months    : plateau, hold at peak
      otherwise                                 : descent peak -> initial over descent_months

    `t` is the month offset (0, 3, 6, ... in the V1 quarterly grid). Returns a
    rate fraction. No rounding.
    """
    months_to_peak = stress_timing["months_to_peak"]
    plateau = stress_timing["plateau_months"]
    descent = stress_timing["descent_months"]

    if t <= months_to_peak:
        return interpolate(initial, peak, t / months_to_peak)
    elif t <= months_to_peak + plateau:
        return peak
    else:
        progress = (t - months_to_peak - plateau) / descent
        return interpolate(peak, initial, progress)
