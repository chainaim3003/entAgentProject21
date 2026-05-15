"""
actus_mentor_client.py — HTTP client for ACTUS-Mentor /generate-xbrl-report.

ACTUS Mentor's api_server.py exposes /generate-xbrl-report as a DETERMINISTIC
templating endpoint — it maps ACTUS cash flow events to IFRS / US-GAAP XBRL
fields via xbrl_output_generator.py. Does NOT call the 9-node RAG pipeline.
This is the right wing of the bow-tie: structured in, regulator-grade artifact out.

CONTRACT (verified by reading ACTUS-MENTOR-MCP/backend/api_server.py):
  POST {ACTUS_MENTOR_URL}/generate-xbrl-report
  Headers: X-API-Key (optional — required only if ACTUS Mentor has API_SECRET_KEY set)
  Body: {
    "actus_events":  [...],          # events from the DRAPS simulation
    "contract_info": {...},          # loan + market context
    "taxonomy":      "ifrs" | "usgaap" | "both",
  }
  Returns: dict produced by xbrl_output_generator.generate_xbrl_report
           (includes a "summary" block, plus per-taxonomy structured documents)
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import httpx

from config import settings

logger = logging.getLogger("actus_mentor_client")

Taxonomy = Literal["ifrs", "usgaap", "both"]


def generate_xbrl_report(
    *,
    events: list[dict[str, Any]],
    contract_info: dict[str, Any],
    taxonomy: Taxonomy = "both",
) -> dict[str, Any]:
    """Call ACTUS-Mentor /generate-xbrl-report.

    Args:
        events:        ACTUS cash flow events from the DRAPS simulation
                       (state.simulation_result.events).
        contract_info: original contract details (loan + market).
        taxonomy:      'ifrs' | 'usgaap' | 'both'.

    Returns:
        The full XBRL report dict produced by xbrl_output_generator. Includes
        a "summary" block and per-taxonomy structured documents (IFRS, US-GAAP).

    Raises:
        RuntimeError: if ACTUS Mentor is unreachable or returns non-200.
            We never fabricate a disclosure document.
    """
    url = f"{settings.actus_mentor_url.rstrip('/')}/generate-xbrl-report"
    payload = {
        "actus_events":  events,
        "contract_info": contract_info,
        "taxonomy":      taxonomy,
    }

    headers: dict[str, str] = {}
    api_key = getattr(settings, "actus_mentor_api_key", "") or ""
    if api_key:
        headers["X-API-Key"] = api_key

    logger.info(
        "actus_mentor_client: POST %s (taxonomy=%s, events=%d)",
        url, taxonomy, len(events),
    )

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=payload, headers=headers)
    except httpx.RequestError as e:
        raise RuntimeError(
            f"ACTUS-Mentor unreachable at {url}: {e}. "
            "Is the ACTUS-Mentor uvicorn server running on the configured port?"
        ) from e

    if resp.status_code == 401:
        raise RuntimeError(
            "ACTUS-Mentor returned 401 Unauthorized. "
            "Set ACTUS_MENTOR_API_KEY in .env if ACTUS-Mentor has API_SECRET_KEY enabled."
        )

    if resp.status_code != 200:
        body = resp.text[:500]
        raise RuntimeError(
            f"ACTUS-Mentor /generate-xbrl-report returned HTTP {resp.status_code}: {body}"
        )

    try:
        return resp.json()
    except Exception as e:
        raise RuntimeError(
            f"ACTUS-Mentor returned non-JSON response: {resp.text[:300]}"
        ) from e
