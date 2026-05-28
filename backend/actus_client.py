"""
actus_client.py — HTTP client for the ACTUS risk engine /eventsBatch (v2_direct path).

ITERATION-6a SCOPE (D3):
  When the composer runs dispatch='v2_direct' (mode='derived'), it derives the SOFR
  path + the two swap fixed rates IN V2 and hands them to the simulation node on
  `knot_payload['v2_direct']`. There is NO DRAPS roundtrip on this path. This module
  is the piece that draps_client.py is for the draps_v1 path: it builds the three
  scenario contract batches (A no-hedge, B swap-now, C swap-later), POSTs each
  DIRECTLY to the ACTUS risk engine's /eventsBatch endpoint, and aggregates the
  per-scenario events into the {A_total, B_total, C_total, ...} shape the rest of
  the bow-tie expects.

AUTHORITATIVE SOURCE (transcribed verbatim from the Postman prerequest "exec" arrays):
  DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json
  In the draps_v1 path, DRAPS runs those exact prerequest scripts to build the ACTUS
  payloads and the test scripts to aggregate. v2_direct bypasses DRAPS, so this module
  REPLICATES both in Python. Two details that the older handoff transcription got wrong
  and that ARE replicated correctly here from the source:
    1. statusDate carries the 'T00:00:00' suffix (it is `deal_str + 'T00:00:00'`,
       NOT the bare date string).
    2. The scenario-C FLOAT-leg `sofr_at_swap` defaults to sofr_path[0].value
       (the FIRST point) when no path point is >= swap_start — NOT the last point.
       (The composer's _lookup_sofr falls back to the LAST point, but that helper
       only feeds the FIXED rates, which we consume verbatim and do not recompute.)

NO LLM IMPORTS — deterministic by design (agent-type law; same constraint as draps_client).

BYTE-EQUALITY (D5) NOTES — flagged honestly, NOT silently assumed:
  • ACTUS computes events from the NUMERIC semantics of the contract, so the
    events digest is driven by the rate VALUES (rounded to 4dp via toFixed-equivalent)
    and the DATE strings — not by JSON key order or by string-vs-number formatting
    of a numeric field. We still mirror the Postman's string forms where cheap.
  • Loan maturity is computed via draps_client._months_to_maturity_date so the
    v2_direct path anchors on the IDENTICAL maturity date that the draps_v1 path
    sends to ACTUS (D5 compares the two). Imported rather than re-implemented to
    prevent drift.
  • Month arithmetic for first_payment / swap_start / first_swap_payment uses
    JS Date.setMonth OVERFLOW-forward semantics (see _add_months), matching the
    Postman addMonths(). Maturity uses the CLAMP semantics of draps_client because
    that is how draps_v1 derives the maturity it feeds DRAPS. The two differ only
    for day-of-month > 28 starts; typical loan_start='YYYY-MM-01' is unaffected.
  • Timezone: the Postman addMonths() round-trips through new Date(...).toISOString()
    (UTC). Our Python date math is timezone-naive. These agree iff DRAPS's Node
    process runs in UTC (the usual CI/server case). If D5 surfaces a 1-day date
    drift, this is the first suspect.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import httpx

from config import settings

# Loan maturity MUST be computed identically to the draps_v1 path so both dispatch
# paths anchor on the same maturityDate (D5 byte-equality). Single source of truth.
from draps_client import _months_to_maturity_date  # noqa: PLC2701  (intentional reuse)

logger = logging.getLogger("actus_client")

# Risk-factor market object code — fixed across all payloads (matches the Postman).
_MARKET_OBJECT_CODE = "DETERIORATING_SOFR"
# Swap-now is structurally anchored to loan_start in the Postman (offset is reflected
# in the swap_now_fixed RATE the composer already computed, not in B's contract dates).
_LOAN_FIRST_PAYMENT_OFFSET_MONTHS = 3
_SWAP_FIRST_PAYMENT_OFFSET_MONTHS = 3


# ──────────────────────────────────────────────────────────────────────────────
# Date / number formatting helpers (JS-faithful)
# ──────────────────────────────────────────────────────────────────────────────

def _add_months(d: date, n: int) -> date:
    """JS `Date.setMonth(getMonth()+n)` overflow-forward semantics.

    Keeps the day-of-month and overflows forward (e.g. Jan31 + 1mo -> Mar 3),
    NOT clamped. Identical to composer._add_months so v2_direct's first_payment /
    swap dates match what the composer used to anchor the SOFR grid.
    """
    total = d.year * 12 + (d.month - 1) + n
    y, m0 = divmod(total, 12)
    return date(y, m0 + 1, 1) + timedelta(days=d.day - 1)


def _minus_one_day(d: date) -> date:
    return d - timedelta(days=1)


def _iso(d: date) -> str:
    return d.isoformat()


def _t(date_str: str) -> str:
    """Append the ACTUS 'T00:00:00' suffix to a 'YYYY-MM-DD' string."""
    return f"{date_str}T00:00:00"


def _to_fixed4(x: float) -> str:
    """Emulate JS Number.prototype.toFixed(4): half-away-from-zero, 4 fixed decimals.

    Returns a STRING with exactly 4 decimal places (e.g. 0.073 -> '0.0730'), matching
    the Postman which assigns the toFixed(4) result directly to nominalInterestRate.
    Mirrors composer._round4's rounding (Decimal(repr(x)).quantize ROUND_HALF_UP) so
    the SOFR-derived rates round identically on both dispatch paths.
    """
    return str(Decimal(repr(x)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _num_str(x: float) -> str:
    """Shortest clean decimal string for a numeric field passed through as-is.

    Used for rateSpread (the Postman passes the loan_spread collection-variable
    string, e.g. '0.025'). ACTUS parses this numerically, so the exact string form
    is immaterial to the events digest; we still produce a tidy value.
    """
    s = f"{x:.10f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _fmt_notional(notional: float) -> str:
    """Format notional as the Postman does (collection variable string, e.g. '1000000').

    Integral notionals render without a trailing '.0' to match the Postman wire form.
    """
    if float(notional).is_integer():
        return str(int(notional))
    return _num_str(notional)


def _lookup_sofr_at_swap(sofr_path: list[dict], swap_start: date) -> float:
    """Replicate the scenario-C FLOAT-leg lookup VERBATIM from the Postman.

    JS:
        let sofr_at_swap = sofr_path[0].value;            // default = FIRST point
        for (i ...) { if (pathDate >= swapDate) { sofr_at_swap = path[i].value; break; } }

    NOTE: the default is the FIRST point, not the last. (composer._lookup_sofr uses
    the LAST point as fallback, but that is only used to price the FIXED rates, which
    we receive precomputed in knot_payload['v2_direct'] and never recompute here.)
    """
    val = sofr_path[0]["value"]
    for pt in sofr_path:
        if date.fromisoformat(str(pt["time"])[:10]) >= swap_start:
            val = pt["value"]
            break
    return val


# ──────────────────────────────────────────────────────────────────────────────
# Contract builders (field-for-field with the Postman prerequest scripts)
# ──────────────────────────────────────────────────────────────────────────────

def _loan_pam(
    contract_id: str,
    sofr0: float,
    loan_spread: float,
    notional_str: str,
    deal_str: str,
    loan_start_str: str,
    loan_maturity_str: str,
    first_payment_str: str,
) -> dict[str, Any]:
    """The floating-rate loan PAM. Identical across A/B/C except contractID."""
    return {
        "contractType": "PAM",
        "contractID": contract_id,
        "contractRole": "RPA",
        "contractDealDate": _t(deal_str),
        "statusDate": _t(deal_str),
        "initialExchangeDate": _t(loan_start_str),
        "maturityDate": _t(loan_maturity_str),
        "notionalPrincipal": notional_str,
        "currency": "USD",
        "dayCountConvention": "30E360",
        "nominalInterestRate": _to_fixed4(sofr0 + loan_spread),
        "cycleOfInterestPayment": "P3ML1",
        "cycleAnchorDateOfInterestPayment": _t(first_payment_str),
        "cycleOfRateReset": "P3ML1",
        "cycleAnchorDateOfRateReset": _t(loan_start_str),
        "marketObjectCodeOfRateReset": _MARKET_OBJECT_CODE,
        "rateSpread": _num_str(loan_spread),
        "rateMultiplier": "1.0",
    }


def _swap_fixed_leg(
    contract_id: str,
    fixed_rate: float,
    notional_str: str,
    deal_str: str,
    anchor_start_str: str,
    maturity_str: str,
    first_payment_str: str,
) -> dict[str, Any]:
    """FIXED leg of a SWAPS contract (referenceRole FIL). No rate reset."""
    return {
        "object": {
            "contractType": "PAM",
            "contractID": contract_id,
            "contractDealDate": _t(deal_str),
            "initialExchangeDate": _t(anchor_start_str),
            "currency": "USD",
            "statusDate": _t(deal_str),
            "notionalPrincipal": notional_str,
            "dayCountConvention": "30E360",
            "nominalInterestRate": _to_fixed4(fixed_rate),
            "maturityDate": _t(maturity_str),
            "cycleAnchorDateOfInterestPayment": _t(first_payment_str),
            "cycleOfInterestPayment": "P3ML1",
            "premiumDiscountAtIED": "0",
        },
        "referenceType": "CNT",
        "referenceRole": "FIL",
    }


def _swap_float_leg(
    contract_id: str,
    float_rate: float,
    notional_str: str,
    deal_str: str,
    anchor_start_str: str,
    maturity_str: str,
    first_payment_str: str,
) -> dict[str, Any]:
    """FLOAT leg of a SWAPS contract (referenceRole SEL). Resets off DETERIORATING_SOFR."""
    return {
        "object": {
            "contractType": "PAM",
            "contractID": contract_id,
            "contractDealDate": _t(deal_str),
            "initialExchangeDate": _t(anchor_start_str),
            "currency": "USD",
            "statusDate": _t(deal_str),
            "notionalPrincipal": notional_str,
            "dayCountConvention": "30E360",
            "nominalInterestRate": _to_fixed4(float_rate),
            "maturityDate": _t(maturity_str),
            "cycleAnchorDateOfInterestPayment": _t(first_payment_str),
            "cycleOfInterestPayment": "P3ML1",
            "cycleOfRateReset": "P3ML1",
            "cycleAnchorDateOfRateReset": _t(anchor_start_str),
            "marketObjectCodeOfRateReset": _MARKET_OBJECT_CODE,
            "rateMultiplier": "1.0",
            "rateSpread": "0.0",
            "premiumDiscountAtIED": "0",
        },
        "referenceType": "CNT",
        "referenceRole": "SEL",
    }


def _risk_factors(sofr_path: list[dict]) -> list[dict[str, Any]]:
    return [{"marketObjectCode": _MARKET_OBJECT_CODE, "base": 1.0, "data": sofr_path}]


# ──────────────────────────────────────────────────────────────────────────────
# Scenario payload builders
# ──────────────────────────────────────────────────────────────────────────────

def _build_payload_a(ctx: dict[str, Any]) -> dict[str, Any]:
    """Scenario A — no hedge: a single floating-rate loan (LOAN-FLOAT-ONLY)."""
    loan = _loan_pam(
        "LOAN-FLOAT-ONLY", ctx["sofr0"], ctx["loan_spread"], ctx["notional_str"],
        ctx["deal_str"], ctx["loan_start_str"], ctx["loan_maturity_str"], ctx["first_payment_str"],
    )
    return {"contracts": [loan], "riskFactors": _risk_factors(ctx["sofr_path"])}


def _build_payload_b(ctx: dict[str, Any]) -> dict[str, Any]:
    """Scenario B — swap NOW: loan (LOAN-FLOAT-B) + SWAP-NOW-B anchored to loan_start."""
    loan = _loan_pam(
        "LOAN-FLOAT-B", ctx["sofr0"], ctx["loan_spread"], ctx["notional_str"],
        ctx["deal_str"], ctx["loan_start_str"], ctx["loan_maturity_str"], ctx["first_payment_str"],
    )
    swap = {
        "contractType": "SWAPS",
        "contractID": "SWAP-NOW-B",
        "contractRole": "PFL",
        "currency": "USD",
        "contractDealDate": _t(ctx["deal_str"]),
        "statusDate": _t(ctx["deal_str"]),
        "deliverySettlement": "D",
        "contractStructure": [
            _swap_fixed_leg(
                "SWAP-B-FIXED", ctx["swap_now_fixed"], ctx["notional_str"],
                ctx["deal_str"], ctx["loan_start_str"], ctx["loan_maturity_str"], ctx["first_payment_str"],
            ),
            _swap_float_leg(
                "SWAP-B-FLOAT", ctx["sofr0"], ctx["notional_str"],
                ctx["deal_str"], ctx["loan_start_str"], ctx["loan_maturity_str"], ctx["first_payment_str"],
            ),
        ],
    }
    return {"contracts": [loan, swap], "riskFactors": _risk_factors(ctx["sofr_path"])}


def _build_payload_c(ctx: dict[str, Any]) -> dict[str, Any]:
    """Scenario C — swap LATER: loan (LOAN-FLOAT-C) + SWAP-LATER-C anchored to swap_start.

    swap_start = loan_start + swap_later_offset_months; the loan leg stays anchored
    to loan_start. sofr_at_swap is looked up off the SOFR path at swap_start.
    """
    loan = _loan_pam(
        "LOAN-FLOAT-C", ctx["sofr0"], ctx["loan_spread"], ctx["notional_str"],
        ctx["deal_str"], ctx["loan_start_str"], ctx["loan_maturity_str"], ctx["first_payment_str"],
    )
    swap = {
        "contractType": "SWAPS",
        "contractID": "SWAP-LATER-C",
        "contractRole": "PFL",
        "currency": "USD",
        "contractDealDate": _t(ctx["swap_deal_str"]),
        "statusDate": _t(ctx["swap_deal_str"]),
        "deliverySettlement": "D",
        "contractStructure": [
            _swap_fixed_leg(
                "SWAP-C-FIXED", ctx["swap_later_fixed"], ctx["notional_str"],
                ctx["swap_deal_str"], ctx["swap_start_str"], ctx["loan_maturity_str"],
                ctx["first_swap_payment_str"],
            ),
            _swap_float_leg(
                "SWAP-C-FLOAT", ctx["sofr_at_swap"], ctx["notional_str"],
                ctx["swap_deal_str"], ctx["swap_start_str"], ctx["loan_maturity_str"],
                ctx["first_swap_payment_str"],
            ),
        ],
    }
    return {"contracts": [loan, swap], "riskFactors": _risk_factors(ctx["sofr_path"])}


# ──────────────────────────────────────────────────────────────────────────────
# Aggregation (replicates the Postman per-scenario "test" scripts)
# ──────────────────────────────────────────────────────────────────────────────

def _find_contract(response: list[dict], contract_id: str) -> dict[str, Any]:
    """Locate a contract object by contractID in an /eventsBatch response array.

    Raises honestly if absent — we never fabricate a missing leg's cashflows.
    """
    for c in response:
        if isinstance(c, dict) and c.get("contractID") == contract_id:
            return c
        # Some ACTUS error rows omit contractID; surface their message honestly.
    raise RuntimeError(
        f"actus_client: contractID {contract_id!r} not found in /eventsBatch response. "
        f"Present contractIDs: {[c.get('contractID') for c in response if isinstance(c, dict)]}. "
        f"Refusing to aggregate a scenario with a missing leg (invariant: no fabricated totals)."
    )


def _ip_events(contract: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        e for e in (contract.get("events") or [])
        if isinstance(e, dict) and e.get("type") == "IP"
    ]


def _loan_leg_abs(contract: dict[str, Any]) -> float:
    """Loan interest = sum of ABS(payoff) over IP events (the no-hedge cost basis)."""
    return sum(abs(float(e["payoff"])) for e in _ip_events(contract))


def _swap_leg_signed(contract: dict[str, Any]) -> float:
    """Swap gain/loss = sum of SIGNED payoff over IP events (net hedge effect)."""
    return sum(float(e["payoff"]) for e in _ip_events(contract))


# ──────────────────────────────────────────────────────────────────────────────
# HTTP
# ──────────────────────────────────────────────────────────────────────────────

def _post_events_batch(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """POST one scenario payload to {actus_server_url}/eventsBatch.

    Mirrors draps_client.run_simulation's error handling: honest RuntimeError on
    unreachable host, non-200, non-JSON, or unexpected shape. Never fabricates.
    """
    url = f"{settings.actus_server_url.rstrip('/')}/eventsBatch"
    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(url, json=payload)
    except httpx.RequestError as e:
        raise RuntimeError(
            f"ACTUS risk engine unreachable at {url}: {e}. "
            "Is the ACTUS server running on :8083 (or wherever ACTUS_SERVER_URL points)?"
        ) from e

    if resp.status_code != 200:
        raise RuntimeError(
            f"ACTUS /eventsBatch returned HTTP {resp.status_code}: {resp.text[:500]}"
        )

    try:
        data = resp.json()
    except Exception as e:  # noqa: BLE001 — surface any decode failure honestly
        raise RuntimeError(f"ACTUS returned non-JSON response: {resp.text[:300]}") from e

    if not isinstance(data, list):
        raise RuntimeError(
            f"ACTUS /eventsBatch expected a JSON array of contracts; "
            f"got {type(data).__name__}: {str(data)[:300]}"
        )
    return data


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────────

def _swap_later_offset_months(resolved_hedge_spec: dict[str, Any]) -> int:
    """Derive the swap-later offset from the hedge spec exactly as the composer does.

    Mirrors composer._apply_fixed_rate_rule: take the swap scenarios carrying
    'swap_offset_months', sort ascending, the SECOND one is "later". The composer
    used this same offset to price swap_later_fixed, so reading it here keeps the
    contract dates consistent with the fixed rate we were handed.
    """
    swap_scn = [
        s for s in (resolved_hedge_spec.get("scenarios") or [])
        if isinstance(s, dict) and "swap_offset_months" in s
    ]
    swap_scn.sort(key=lambda s: s["swap_offset_months"])
    if len(swap_scn) < 2:
        raise RuntimeError(
            "actus_client (v2_direct): resolved_hedge_spec must carry >=2 swap scenarios "
            f"with 'swap_offset_months' to anchor scenario C; found {len(swap_scn)}."
        )
    return int(swap_scn[1]["swap_offset_months"])


def run_v2_direct(
    knot_payload: dict[str, Any],
    resolved_hedge_spec: dict[str, Any],
) -> dict[str, Any]:
    """Build + POST the three v2_direct scenario batches and aggregate the results.

    Args:
        knot_payload: the composer's output. Reads:
            knot_payload['v2_direct'] = {sofr_path, swap_now_fixed, swap_later_fixed}
            knot_payload['loan']      = {notional_usd, spread_bps, term_months, start_date, ...}
        resolved_hedge_spec: used only to derive the swap-later offset (months).

    Returns:
        {
          "A_total", "B_total", "C_total": float,
          "A_loan", "A_swap", "B_loan", "B_swap", "C_loan", "C_swap": float,
          "events": list[dict],            # all events across A/B/C (richer than draps_v1)
          # carried through so the N6a Provenance Agent sees the same numerics:
          "sofr_path": list[dict],
          "swap_now_fixed_rate": float,
          "swap_later_fixed_rate": float,
        }

    Raises:
        RuntimeError: on missing knot fields, unreachable/erroring ACTUS, or a
            missing contract leg in any response. Never fabricates a total.
    """
    v2 = knot_payload.get("v2_direct")
    if not isinstance(v2, dict):
        raise RuntimeError(
            "actus_client.run_v2_direct called without knot_payload['v2_direct']. "
            "This path is only reachable when the composer ran dispatch='v2_direct'."
        )
    for key in ("sofr_path", "swap_now_fixed", "swap_later_fixed"):
        if key not in v2:
            raise RuntimeError(f"actus_client (v2_direct): knot_payload['v2_direct'] missing {key!r}.")

    sofr_path = v2["sofr_path"]
    if not isinstance(sofr_path, list) or not sofr_path:
        raise RuntimeError("actus_client (v2_direct): knot_payload['v2_direct']['sofr_path'] must be a non-empty list.")
    swap_now_fixed = float(v2["swap_now_fixed"])
    swap_later_fixed = float(v2["swap_later_fixed"])

    loan = knot_payload.get("loan") or {}
    try:
        notional = float(loan["notional_usd"])
        spread_bps = float(loan["spread_bps"])
        term_months = int(loan["term_months"])
        loan_start = date.fromisoformat(str(loan["start_date"])[:10])
    except (KeyError, TypeError, ValueError) as e:
        raise RuntimeError(
            f"actus_client (v2_direct): knot_payload['loan'] missing/invalid required field: {e}. "
            f"Have: {sorted(loan.keys())}."
        ) from e

    # loan_spread (decimal) = spread_bps / 10000. Verified against validator_node, which
    # is the sole producer of validated_inputs['loan']['spread_bps'] (basis points), and
    # against the draps_v1 corridor value loan_spread=0.025 (= 250 bps).
    loan_spread = spread_bps / 10000.0
    sofr0 = float(sofr_path[0]["value"])

    # --- common loan dates (anchored to loan_start) ---
    loan_start_str = _iso(loan_start)
    loan_maturity_str = _months_to_maturity_date(loan_start_str, term_months)
    deal_str = _iso(_minus_one_day(loan_start))
    first_payment_str = _iso(_add_months(loan_start, _LOAN_FIRST_PAYMENT_OFFSET_MONTHS))

    # --- scenario-C swap dates (anchored to swap_start = loan_start + later_offset) ---
    later_offset = _swap_later_offset_months(resolved_hedge_spec)
    swap_start = _add_months(loan_start, later_offset)
    swap_start_str = _iso(swap_start)
    swap_deal_str = _iso(_minus_one_day(swap_start))
    first_swap_payment_str = _iso(_add_months(swap_start, _SWAP_FIRST_PAYMENT_OFFSET_MONTHS))
    sofr_at_swap = _lookup_sofr_at_swap(sofr_path, swap_start)

    ctx = {
        "sofr_path": sofr_path,
        "sofr0": sofr0,
        "loan_spread": loan_spread,
        "notional_str": _fmt_notional(notional),
        "loan_start_str": loan_start_str,
        "loan_maturity_str": loan_maturity_str,
        "deal_str": deal_str,
        "first_payment_str": first_payment_str,
        "swap_now_fixed": swap_now_fixed,
        "swap_later_fixed": swap_later_fixed,
        "swap_start_str": swap_start_str,
        "swap_deal_str": swap_deal_str,
        "first_swap_payment_str": first_swap_payment_str,
        "sofr_at_swap": sofr_at_swap,
    }

    payload_a = _build_payload_a(ctx)
    payload_b = _build_payload_b(ctx)
    payload_c = _build_payload_c(ctx)

    logger.info("actus_client: POST v2_direct A/B/C to %s/eventsBatch",
                settings.actus_server_url.rstrip("/"))

    resp_a = _post_events_batch(payload_a)
    resp_b = _post_events_batch(payload_b)
    resp_c = _post_events_batch(payload_c)

    # --- aggregate (Postman test-script rule) ---
    a_loan = _loan_leg_abs(_find_contract(resp_a, "LOAN-FLOAT-ONLY"))
    a_total = a_loan
    a_swap = 0.0

    b_loan = _loan_leg_abs(_find_contract(resp_b, "LOAN-FLOAT-B"))
    b_swap = _swap_leg_signed(_find_contract(resp_b, "SWAP-NOW-B"))
    b_total = b_loan - b_swap

    c_loan = _loan_leg_abs(_find_contract(resp_c, "LOAN-FLOAT-C"))
    c_swap = _swap_leg_signed(_find_contract(resp_c, "SWAP-LATER-C"))
    c_total = c_loan - c_swap

    events: list[dict] = []
    for resp in (resp_a, resp_b, resp_c):
        for contract in resp:
            if isinstance(contract, dict) and isinstance(contract.get("events"), list):
                events.extend(contract["events"])

    return {
        "A_total": a_total, "B_total": b_total, "C_total": c_total,
        "A_loan": a_loan, "A_swap": a_swap,
        "B_loan": b_loan, "B_swap": b_swap,
        "C_loan": c_loan, "C_swap": c_swap,
        "events": events,
        "sofr_path": sofr_path,
        "swap_now_fixed_rate": swap_now_fixed,
        "swap_later_fixed_rate": swap_later_fixed,
    }
