"""
actus_mentor_client.py — HTTP client for ACTUS-Mentor /generate-xbrl-report.

Single source of truth for the ACTUS-Mentor REST interface used by N6 Disclosure.

CURRENT STATUS: NotImplementedError.
The /generate-xbrl-report endpoint is *classified* deterministic-templating in the design,
but the exact request/response shape has not been verified by reading api_server.py.

To complete:
  1. Read ACTUS-Mentor's api_server.py to confirm:
       - exact path (/generate-xbrl-report assumed)
       - exact request body {actus_events, contract_info, taxonomy}
       - exact response shape (likely a wrapper around the XBRL document(s))
  2. Confirm the endpoint is deterministic templating, NOT the 7-agent RAG graph.
       If it IS the RAG graph, the Disclosure Agent must be reclassified as reasoning
       and moved to reasoning_agents.py (per DESIGN/DESIGN1/design-1-detailed-design.md §6 note 2).
  3. Implement the call below.

Reference: DESIGN/DESIGN1/design-1-detailed-design.md §6 note 2.
"""

from __future__ import annotations

from typing import Any, Literal

from config import settings


Taxonomy = Literal["ifrs", "usgaap", "both"]


def generate_xbrl_report(
    *,
    events: list[dict[str, Any]],
    contract_info: dict[str, Any],
    taxonomy: Taxonomy = "both",
) -> dict[str, Any]:
    """Call ACTUS-Mentor /generate-xbrl-report.

    Args:
        events:        ACTUS events list from the DRAPS simulation (state.simulation_result.events).
        contract_info: original contract details (loan + market).
        taxonomy:      'ifrs' | 'usgaap' | 'both'.

    Returns:
        {
          "taxonomies": ["ifrs", "usgaap"],
          "ifrs":   {<XBRL document or its serialization>},
          "usgaap": {<XBRL document or its serialization>},
        }

    Raises:
        NotImplementedError: the ACTUS-Mentor /generate-xbrl-report endpoint contract
            is not yet verified.
    """
    # When implementing:
    #   import httpx
    #   url = f"{settings.actus_mentor_url}/generate-xbrl-report"
    #   payload = {
    #       "actus_events":  events,
    #       "contract_info": contract_info,
    #       "taxonomy":      taxonomy,
    #   }
    #   with httpx.Client(timeout=60.0) as client:
    #       resp = client.post(url, json=payload)
    #       resp.raise_for_status()
    #       return resp.json()
    raise NotImplementedError(
        "ACTUS-Mentor /generate-xbrl-report contract not yet verified. "
        "See DESIGN/DESIGN1/design-1-detailed-design.md §6 note 2. "
        "Required reads before implementation: ACTUS-Mentor api_server.py to confirm "
        "the endpoint is deterministic templating (not the 7-agent RAG graph). "
        f"Target endpoint: {settings.actus_mentor_url}/generate-xbrl-report"
    )
