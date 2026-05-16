"""
draps_client.py — HTTP client for DRAPS /api/simulate.

DRAPS exposes a plain HTTP REST server (Express, src/server.ts) on the configured URL.
This file POSTs validated loan + market context to DRAPS and returns the
{A_total, B_total, C_total, events} shape that the rest of the bow-tie expects.

NOTE on the env var name:
  The variable is called `DRAPS_MCP_URL` in config.py for historical reasons (the
  original design assumed MCP transport). DRAPS actually speaks plain HTTP. The
  variable still works — it's the same URL — just misnamed. Cosmetic rename deferred.

CONTRACT (verified by reading SWAPS-interface/Backend/src/routes/simulation.routes.ts):
  POST {DRAPS_URL}/api/simulate
  Body: { configData: { config_metadata: {config_id, collection_file}, ...primary_vars } }
  Returns: a simulation result object (shape parsed defensively below)

Reference: SWAPS-1LOAN-WHAT-IF-DEMO.json (the Postman collection that defines primary variables).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from config import settings

logger = logging.getLogger("draps_client")

# The Postman collection file that seeds the simulation.
# OPTION 2 (inline contract): the file now lives INSIDE entAgent at
# entAgentProject21/DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json. Single source of truth.
# We read it here and ship the FULL CONTENT to DRAPS under `collection_inline`,
# so DRAPS never touches its own disk for this file. See CHANGES-OPTION2.md.
_DEFAULT_COLLECTION = "SWAPS-1LOAN-WHAT-IF-DEMO.json"
_COLLECTION_PATH = (
    Path(__file__).resolve().parent.parent / "DATA" / _DEFAULT_COLLECTION
)


def _load_collection_content() -> dict[str, Any]:
    """Read SWAPS-1LOAN-WHAT-IF-DEMO.json from entAgent/DATA and return its parsed content.

    Raises:
        FileNotFoundError: if the file is missing — honest failure, no fallback.
        json.JSONDecodeError: if the file is malformed — honest failure, no fallback.
    """
    if not _COLLECTION_PATH.is_file():
        raise FileNotFoundError(
            f"Collection file not found: {_COLLECTION_PATH}. "
            "Place SWAPS-1LOAN-WHAT-IF-DEMO.json under entAgentProject21/DATA/."
        )
    with _COLLECTION_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

# Scenario offsets that DEFINE A/B/C in the bow-tie architecture (NOT mocked —
# these are the structural definition of the scenarios in the design):
#   A = no hedge       (no swap requested)
#   B = hedge NOW      (swap offset = 0 months from loan start)
#   C = hedge LATER    (swap offset = 3 months from loan start)
_SWAP_NOW_OFFSET_MONTHS = 0
_SWAP_LATER_OFFSET_MONTHS = 3


def _months_to_maturity_date(start_date_iso: str, term_months: int) -> str:
    """Add term_months to an ISO date string. Returns ISO date string.

    Manual calculation — avoids adding a dateutil dependency.
    """
    start = datetime.fromisoformat(start_date_iso)
    total_months = start.month - 1 + term_months
    year = start.year + total_months // 12
    month = total_months % 12 + 1
    day = start.day
    # Clamp day for short months
    if month in (4, 6, 9, 11) and day == 31:
        day = 30
    elif month == 2 and day > 28:
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        day = 29 if is_leap else 28
    return f"{year:04d}-{month:02d}-{day:02d}"


def _build_config_data(validated: dict[str, Any]) -> dict[str, Any]:
    """Translate Hedge Advisor's validated_inputs into DRAPS's configData shape.

    Maps the cross-product of (Hedge Advisor schema) ↔ (DRAPS Postman variables).
    """
    loan = validated.get("loan", {})
    market = validated.get("market", {})

    notional = loan.get("notional_usd")
    start_date = loan.get("start_date")
    term_months = loan.get("term_months")
    maturity_date = _months_to_maturity_date(start_date, term_months)

    corridor = market.get("corridor") or {}
    exporter = corridor.get("origin")
    importer = corridor.get("destination")
    commodity = market.get("gtap_commodity_code")
    tariff = market.get("tariff_assumption_pct")

    # Hedge Advisor's N2 produces a single tariff assumption. DRAPS expects both
    # `tariff_current` and `tariff_peak`. We send the same value for both, which
    # simulates a flat tariff (no escalation scenario). To enable tariff escalation:
    # extend N2 Market Context to emit `tariff_current` and `tariff_peak` separately.
    tariff_current = tariff if tariff is not None else 0.0
    tariff_peak = tariff_current

    # Inline the collection content (Option 2 contract). DRAPS reads
    # config_metadata.collection_inline if present and skips its own disk load.
    # collection_file is kept ONLY as a label for logging/audit on the DRAPS side.
    collection_content = _load_collection_content()

    return {
        "config_metadata": {
            "config_id": f"hedge-advisor-{notional}-{commodity}",
            "collection_file": _DEFAULT_COLLECTION,
            "collection_inline": collection_content,
        },
        "jurisdiction": {
            "source": "file",
            "file": "jurisdictions/us-genius.json",
        },
        "simulation_timeframe": {
            "start_date": start_date,
            "end_date": maturity_date,
            "frequency": "monthly",
        },
        "loan_notional": notional,
        "loan_start_date": start_date,
        "loan_maturity_date": maturity_date,
        "exporter_country": exporter,
        "importer_country": importer,
        "commodity_code": commodity,
        "tariff_current": tariff_current,
        "tariff_peak": tariff_peak,
        "swap_now_offset_months": _SWAP_NOW_OFFSET_MONTHS,
        "swap_later_offset_months": _SWAP_LATER_OFFSET_MONTHS,
    }


def _extract_scenarios(response_json: dict[str, Any]) -> dict[str, Any]:
    """Defensively pull A_total, B_total, C_total, events out of DRAPS's response.

    DRAPS's response shape isn't fully documented from the source we've read.
    We try several plausible nesting locations and raise a clear error if none
    match — intentional, so we fail honestly rather than fabricate totals.
    """
    if not isinstance(response_json, dict):
        raise RuntimeError(
            f"DRAPS returned non-object JSON: {type(response_json).__name__}"
        )

    # 0) DRAPS scripted-collection shape — totals are written by test scripts via
    #    pm.environment.set('A_total', …) and exposed under `environmentVariables`.
    #    Values arrive as STRINGS (pm.environment stores them via String(value)).
    def _as_float(v: Any) -> float | None:
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return None

    env_vars = response_json.get("environmentVariables")
    if not isinstance(env_vars, dict):
        # On failure DRAPS wraps the result under "details"
        details = response_json.get("details")
        if isinstance(details, dict):
            env_vars = details.get("environmentVariables")

    if isinstance(env_vars, dict):
        a = _as_float(env_vars.get("A_total"))
        b = _as_float(env_vars.get("B_total"))
        c = _as_float(env_vars.get("C_total"))
        if all(v is not None for v in (a, b, c)):
            # Pull cashflow events from the captured ACTUS POST response, if any.
            sim = response_json.get("simulation")
            if not isinstance(sim, list):
                details = response_json.get("details") or {}
                sim = details.get("simulation") if isinstance(details, dict) else None
            events: list[dict] = []
            if isinstance(sim, list):
                for contract in sim:
                    if isinstance(contract, dict) and isinstance(contract.get("events"), list):
                        events.extend(contract["events"])
            return {"A_total": a, "B_total": b, "C_total": c, "events": events}

    # 1) Flat top-level shape
    flat = {k: response_json.get(k) for k in ("A_total", "B_total", "C_total")}
    if all(isinstance(flat[k], (int, float)) for k in flat):
        events = response_json.get("events") or response_json.get("cashflow_events") or []
        return {**flat, "events": events}

    # 2) Nested under "scenarios"
    scenarios = response_json.get("scenarios")
    if isinstance(scenarios, dict):
        a = (scenarios.get("A") or {}).get("total")
        b = (scenarios.get("B") or {}).get("total")
        c = (scenarios.get("C") or {}).get("total")
        if all(isinstance(v, (int, float)) for v in (a, b, c)):
            events = (
                (scenarios.get("B") or {}).get("events")
                or (scenarios.get("C") or {}).get("events")
                or response_json.get("events")
                or []
            )
            return {"A_total": a, "B_total": b, "C_total": c, "events": events}

    # 3) Nested under "result" or "simulationResult"
    result = response_json.get("result") or response_json.get("simulationResult")
    if isinstance(result, dict):
        a = result.get("A_total") or result.get("a_total")
        b = result.get("B_total") or result.get("b_total")
        c = result.get("C_total") or result.get("c_total")
        if all(isinstance(v, (int, float)) for v in (a, b, c)):
            events = result.get("events") or response_json.get("events") or []
            return {"A_total": a, "B_total": b, "C_total": c, "events": events}

    # Honest failure — DRAPS returned data but the shape isn't recognized
    raise RuntimeError(
        "DRAPS simulation succeeded but the response shape was unexpected. "
        f"Top-level keys: {sorted(response_json.keys())}. "
        "Update draps_client._extract_scenarios() with the actual response path. "
        "Invariant I5: we never fabricate a scenario total."
    )


def run_simulation(validated_inputs: dict[str, Any]) -> dict[str, Any]:
    """Call DRAPS /api/simulate.

    Args:
        validated_inputs: schema-clean inputs from N3 Validator.

    Returns:
        {
          "A_total": float, "B_total": float, "C_total": float,
          "events": list[dict],
        }

    Raises:
        RuntimeError: if DRAPS is unreachable, returns non-200, or returns
            an unrecognized response shape. We never fabricate results.
    """
    config_data = _build_config_data(validated_inputs)
    url = f"{settings.draps_mcp_url.rstrip('/')}/api/simulate"

    logger.info(
        "draps_client: POST %s (config_id=%s)",
        url, config_data["config_metadata"]["config_id"],
    )

    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(url, json={"configData": config_data})
    except httpx.RequestError as e:
        raise RuntimeError(
            f"DRAPS unreachable at {url}: {e}. "
            "Is the DRAPS server running? Run `npm run server` in "
            "SWAPS-interface/Backend (listens on port 4000 by default)."
        ) from e

    if resp.status_code != 200:
        # Surface DRAPS's own error message — don't paper over it
        body = resp.text[:500]
        raise RuntimeError(
            f"DRAPS /api/simulate returned HTTP {resp.status_code}: {body}"
        )

    try:
        data = resp.json()
    except Exception as e:
        raise RuntimeError(
            f"DRAPS returned non-JSON response: {resp.text[:300]}"
        ) from e

    if isinstance(data, dict) and data.get("success") is False:
        raise RuntimeError(
            f"DRAPS simulation reported failure: {data.get('error', 'unknown')}"
        )

    return _extract_scenarios(data)
