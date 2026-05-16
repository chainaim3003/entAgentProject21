"""
run_draps_local.py — Standalone end-to-end check for the Option 2 wiring.

What this proves, step by step:
  1. _COLLECTION_PATH resolves to entAgent/DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json
  2. _load_collection_content() reads + parses that file (the "JSON is fetched" check)
  3. _build_config_data() builds the request body with collection_inline present
  4. The body is POSTed to DRAPS at DRAPS_MCP_URL/api/simulate
  5. DRAPS responds; we save the response and try to extract A/B/C totals

No mocks. No fallbacks. Each step either succeeds or prints exactly why it failed.

Run from the backend folder with the venv activated:
  cd C:\\SATHYA\\CHAINAIM3003\\mcp-servers\\FINAGENTS\\FINAGENTS2\\entAgentProject21\\backend
  .venv\\Scripts\\activate
  python run_draps_local.py
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

# ── Stub env vars BEFORE importing draps_client (config.py reads them on import) ───
# Real DRAPS_MCP_URL comes from .env (loaded by pydantic-settings). We only stub the
# Gemini key here because this script doesn't need an LLM — just the deterministic path.
os.environ.setdefault("GEMINI_API_KEY", "local-script-not-used")
os.environ.setdefault("ACTUS_MENTOR_URL", "http://localhost:8001")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import httpx  # noqa: E402

import draps_client  # noqa: E402
from config import settings  # noqa: E402


# Output folder for inspectable artifacts
OUT_DIR = HERE / "local_run_artifacts"
OUT_DIR.mkdir(exist_ok=True)


def banner(s: str) -> None:
    bar = "=" * 70
    print(f"\n{bar}\n  {s}\n{bar}")


def fail(msg: str) -> None:
    print(f"\n❌ FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────
# STEP 1 — Verify the file path resolves and the JSON loads
# ─────────────────────────────────────────────────────────────────────

banner("STEP 1 — Verify entAgent/DATA/SWAPS-1LOAN-WHAT-IF-DEMO.json loads")

print(f"  Expected path: {draps_client._COLLECTION_PATH}")
print(f"  File exists:   {draps_client._COLLECTION_PATH.is_file()}")

if not draps_client._COLLECTION_PATH.is_file():
    fail(
        f"File not found at {draps_client._COLLECTION_PATH}. "
        "Confirm it was placed in entAgentProject21/DATA/."
    )

try:
    collection = draps_client._load_collection_content()
except Exception as e:
    fail(f"_load_collection_content() raised: {type(e).__name__}: {e}")

print(f"  Parsed OK. Top-level keys: {sorted(collection.keys())}")
print(f"  info.name:                 {collection.get('info', {}).get('name')}")
print(f"  variable count:            {len(collection.get('variable', []))}")
print(f"  item count:                {len(collection.get('item', []))}")
print(f"  event count:               {len(collection.get('event', []))}")

# Spot-check: the JSON's first variable should be exporter_country=India
first_var = (collection.get("variable") or [{}])[0]
print(f"  first variable:            {first_var.get('key')} = {first_var.get('value')!r}")
if first_var.get("key") != "exporter_country" or first_var.get("value") != "India":
    fail("First variable is not exporter_country=India — wrong file or corrupted JSON.")

print("  ✅ JSON is fetched correctly.")


# ─────────────────────────────────────────────────────────────────────
# STEP 2 — Build the DRAPS payload via _build_config_data()
# ─────────────────────────────────────────────────────────────────────

banner("STEP 2 — Build DRAPS request body (with collection_inline)")

# Same fixture shape as backend/tests/test_knot.py — passes the validator.
VALIDATED_INPUTS = {
    "loan": {
        "notional_usd": 1_000_000.0,
        "spread_bps": 250.0,
        "term_months": 24,
        "start_date": "2026-03-01",
        "rate_index": "SOFR",
    },
    "market": {
        "gtap_commodity_code": "tex",
        "corridor": {"origin": "India", "destination": "United States"},
        "tariff_assumption_pct": 0.50,
        "rate_curve_index": "USD-SOFR-FORWARD",
    },
}

try:
    config_data = draps_client._build_config_data(VALIDATED_INPUTS)
except Exception as e:
    fail(f"_build_config_data() raised: {type(e).__name__}: {e}")

meta = config_data.get("config_metadata") or {}
inline_present = isinstance(meta.get("collection_inline"), dict)

print(f"  config_metadata.config_id:          {meta.get('config_id')}")
print(f"  config_metadata.collection_file:    {meta.get('collection_file')}")
print(f"  config_metadata.collection_inline:  {'present (dict)' if inline_present else 'MISSING'}")
print(f"  exporter_country / importer_country: {config_data.get('exporter_country')} / {config_data.get('importer_country')}")
print(f"  commodity_code:                      {config_data.get('commodity_code')}")
print(f"  tariff_current / tariff_peak:        {config_data.get('tariff_current')} / {config_data.get('tariff_peak')}")
print(f"  swap_now_offset_months:              {config_data.get('swap_now_offset_months')}")
print(f"  swap_later_offset_months:            {config_data.get('swap_later_offset_months')}")

if not inline_present:
    fail("collection_inline is missing from config_metadata — Option 2 patch is not active.")

# Save the exact body for inspection
body = {"configData": config_data}
body_path = OUT_DIR / "request_body.json"
with body_path.open("w", encoding="utf-8") as f:
    json.dump(body, f, indent=2, ensure_ascii=False)
body_size_kb = body_path.stat().st_size / 1024
print(f"  Body written to: {body_path}  ({body_size_kb:.1f} KB)")
print("  ✅ Payload built correctly, collection_inline is in the body.")


# ─────────────────────────────────────────────────────────────────────
# STEP 3 — POST to DRAPS and inspect the response
# ─────────────────────────────────────────────────────────────────────

banner(f"STEP 3 — POST to DRAPS at {settings.draps_mcp_url}/api/simulate")

url = f"{settings.draps_mcp_url.rstrip('/')}/api/simulate"
print(f"  URL: {url}")
print(f"  Body size: {body_size_kb:.1f} KB")
print("  Calling (timeout 120s) ...")

try:
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, json=body)
except httpx.ConnectError as e:
    fail(
        f"Cannot reach DRAPS at {url}. Is DRAPS running?\n"
        f"   Start it with: cd SWAPS-interface/Backend && npm run server\n"
        f"   Error: {e}"
    )
except httpx.RequestError as e:
    fail(f"HTTP request error: {type(e).__name__}: {e}")

print(f"  HTTP status: {resp.status_code}")

# Save raw response for inspection regardless of status
raw_path = OUT_DIR / "draps_response_raw.txt"
raw_path.write_text(resp.text, encoding="utf-8")
print(f"  Raw response saved to: {raw_path}  ({len(resp.text)} chars)")

if resp.status_code != 200:
    print(f"  Body preview: {resp.text[:500]}")
    fail(f"DRAPS returned HTTP {resp.status_code} — not 200.")

try:
    data = resp.json()
except Exception as e:
    fail(f"DRAPS response was not JSON: {type(e).__name__}: {e}")

resp_path = OUT_DIR / "draps_response.json"
with resp_path.open("w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"  Parsed JSON saved to: {resp_path}")
print(f"  Response top-level keys: {sorted(data.keys()) if isinstance(data, dict) else type(data).__name__}")


# ─────────────────────────────────────────────────────────────────────
# STEP 4 — Try to extract A/B/C totals (proves DRAPS answered our query)
# ─────────────────────────────────────────────────────────────────────

banner("STEP 4 — Extract A/B/C totals from DRAPS response")

try:
    scenarios = draps_client._extract_scenarios(data)
    print(f"  A_total: ${scenarios['A_total']:,.0f}")
    print(f"  B_total: ${scenarios['B_total']:,.0f}")
    print(f"  C_total: ${scenarios['C_total']:,.0f}")
    print(f"  events:  {len(scenarios.get('events', []))} cashflow events")
    print("  ✅ DRAPS answered the query end-to-end.")
except RuntimeError as e:
    print(f"\n⚠️  _extract_scenarios could not pull totals from the response shape.")
    print(f"   Reason: {e}")
    print(f"   Inspect: {resp_path}")
    print(f"   Then update draps_client._extract_scenarios() to match the actual shape.")
    sys.exit(2)

banner("ALL CHECKS PASSED")
print(f"  Artifacts folder: {OUT_DIR}")
print("  Inspect request_body.json and draps_response.json to see the exchange.")
