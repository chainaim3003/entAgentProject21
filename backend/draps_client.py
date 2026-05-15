"""
draps_client.py — MCP client for DRAPS run_simulation tool.

This is the deterministic knot connector. Single source of truth for the DRAPS interface.

CURRENT STATUS: NotImplementedError.
The exact input/output contract of the DRAPS `run_simulation` MCP tool is not yet verified.

To complete:
  1. Read `SWAPS-interface/Backend/src/mcp-server.ts` from the DRAPS GitHub repo
     (github.com/24pba027-droid/Swaps-for-Supply-Chain-Finance) to confirm:
       - exact tool name ("run_simulation" or similar)
       - exact input schema (likely takes loan + market context + scenarios A/B/C config)
       - exact output schema (must include A_total, B_total, C_total, events for the right wing)
  2. Implement the MCP client connection to DRAPS_MCP_URL (from config.settings.draps_mcp_url).
  3. Implement run_simulation() body to call the MCP tool and shape the output to:
       {"A_total": float, "B_total": float, "C_total": float, "events": list[dict]}

Reference: DESIGN/DESIGN1/design-1-detailed-design.md §6 note 1.
"""

from __future__ import annotations

from typing import Any

from config import settings


def run_simulation(validated_inputs: dict[str, Any]) -> dict[str, Any]:
    """Call DRAPS run_simulation MCP tool.

    Args:
        validated_inputs: schema-clean inputs from N3 Validator. Has shape:
            {
              "loan":   {"notional_usd", "spread_bps", "term_months", "start_date", "rate_index"},
              "market": {"gtap_commodity_code", "corridor", "tariff_assumption_pct", "rate_curve_index"}
            }

    Returns:
        {
          "A_total":   <total cash outflow USD, no-hedge scenario>,
          "B_total":   <total cash outflow USD, hedge-now scenario>,
          "C_total":   <total cash outflow USD, hedge-in-3mo scenario>,
          "events":    <list of ACTUS events for the disclosure agent>,
        }

    Raises:
        NotImplementedError: the DRAPS run_simulation tool contract is not yet verified.
    """
    # When implementing: connect to settings.draps_mcp_url here.
    # Use the `mcp` Python client. Sketch:
    #
    #   from mcp.client.session import ClientSession
    #   from mcp.client.streamable_http import streamablehttp_client
    #
    #   async with streamablehttp_client(settings.draps_mcp_url) as (read, write, _):
    #       async with ClientSession(read, write) as session:
    #           await session.initialize()
    #           result = await session.call_tool(
    #               name="run_simulation",            # confirm exact name in mcp-server.ts
    #               arguments={...validated_inputs}, # confirm exact arg shape in mcp-server.ts
    #           )
    #           # Parse result.content into {A_total, B_total, C_total, events}
    #           return parsed
    #
    # Wrap in asyncio.run() or make this function async + propagate up to the graph.
    raise NotImplementedError(
        "DRAPS run_simulation contract not yet verified. "
        "See DESIGN/DESIGN1/design-1-detailed-design.md §6 note 1. "
        "Required reads before implementation: "
        "SWAPS-interface/Backend/src/mcp-server.ts (GitHub) for exact tool I/O shape. "
        f"Target endpoint: {settings.draps_mcp_url}"
    )
