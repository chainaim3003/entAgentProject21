"""
capture_v1_baseline.py \u2014 Capture the V1 byte-equality baseline.

Reads the most recent DRAPS response captured by run_draps_local.py
(in backend/local_run_artifacts/draps_response.json) and writes the canonical
baseline fixture at backend/tests/fixtures/v1-baseline/india-us-textiles.json.

The fixture is the ground truth that backend/tests/test_byte_equality_v1.py asserts against.

USAGE:
    # 1. Make sure DRAPS and ACTUS are running (Docker containers up).
    # 2. From backend/ with venv activated, run the smoke test once to populate
    #    local_run_artifacts/draps_response.json:
    #        python run_draps_local.py
    # 3. From the repo root, run this capture script:
    #        python scripts/capture_v1_baseline.py
    # 4. Inspect the produced fixture file (paths printed below).

The script is idempotent: re-running overwrites the fixture with the latest captured response.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


# ---- Paths ----
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
ARTIFACTS = REPO_ROOT / "backend" / "local_run_artifacts"
RESPONSE_FILE = ARTIFACTS / "draps_response.json"
REQUEST_FILE = ARTIFACTS / "request_body.json"

FIXTURE_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "v1-baseline"
FIXTURE_FILE = FIXTURE_DIR / "india-us-textiles.json"


# ---- The validated_inputs that produced this baseline (matches run_draps_local.py) ----
BASELINE_VALIDATED_INPUTS = {
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


def fail(msg: str) -> None:
    print(f"\u274c FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def canonical_events_digest(events: list[dict]) -> str:
    """SHA-256 of canonical-JSON-encoded events list.

    canonical = sort_keys=True, no whitespace, UTF-8. Deterministic across runs.
    """
    canon = json.dumps(events, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def extract_swap_fixed_rate(payload_json_str: str, fixed_contract_id: str) -> float | None:
    """Pull the SWAP-?-FIXED nominalInterestRate out of an environmentVariables payload.

    Payload arrives as a JSON string (Postman stores everything as string).
    """
    payload = json.loads(payload_json_str)
    for c in payload.get("contracts", []):
        if c.get("contractType") != "SWAPS":
            continue
        for elem in c.get("contractStructure", []) or []:
            obj = elem.get("object") or {}
            if obj.get("contractID") == fixed_contract_id:
                return float(obj["nominalInterestRate"])
    return None


def main() -> int:
    print(f"  Reading DRAPS response: {RESPONSE_FILE}")
    if not RESPONSE_FILE.is_file():
        fail(
            f"DRAPS response not found at {RESPONSE_FILE}. "
            "Run `python backend/run_draps_local.py` first."
        )

    with RESPONSE_FILE.open("r", encoding="utf-8") as f:
        response = json.load(f)

    if not response.get("success"):
        fail(
            f"Captured response has success=false (DRAPS reported failure). "
            f"Error: {response.get('error')}. Re-run run_draps_local.py with ACTUS up."
        )

    env_vars = response.get("environmentVariables") or {}
    if not env_vars:
        fail("Response has no environmentVariables block. Wrong DRAPS version?")

    # ---- Pull the canonical V1 numbers out of the response ----
    try:
        a_total = float(env_vars["A_total"])
        b_total = float(env_vars["B_total"])
        c_total = float(env_vars["C_total"])
        a_swap = float(env_vars["A_swap"])
        b_swap = float(env_vars["B_swap"])
        c_swap = float(env_vars["C_swap"])
        sofr_path = json.loads(env_vars["SOFR_PATH"])
    except KeyError as e:
        fail(f"Missing expected key in environmentVariables: {e}")
    except (TypeError, ValueError) as e:
        fail(f"Malformed value in environmentVariables: {e}")

    swap_now_fixed = extract_swap_fixed_rate(env_vars["SWAP_NOW_PAYLOAD"], "SWAP-B-FIXED")
    swap_later_fixed = extract_swap_fixed_rate(env_vars["SWAP_LATER_PAYLOAD"], "SWAP-C-FIXED")
    if swap_now_fixed is None or swap_later_fixed is None:
        fail("Could not extract swap_now or swap_later fixed rate from payloads.")

    # ---- Accumulate events the same way draps_client._extract_scenarios does ----
    events: list[dict[str, Any]] = []
    for contract in response.get("simulation") or []:
        if isinstance(contract, dict) and isinstance(contract.get("events"), list):
            events.extend(contract["events"])

    events_count = len(events)
    events_digest = canonical_events_digest(events)

    # ---- Build the fixture ----
    fixture = {
        "$schema_note": "V1 byte-equality baseline for the India-US-textiles case. Authored by scripts/capture_v1_baseline.py.",
        "profile_id": "india-us-textiles-v1",
        "captured_from": {
            "scenario_name": response.get("scenarioName"),
            "draps_response_file": str(RESPONSE_FILE.relative_to(REPO_ROOT)),
            "draps_response_timestamp": response.get("timestamp"),
            "config_metadata": response.get("configMetadata"),
        },
        "validated_inputs": BASELINE_VALIDATED_INPUTS,
        "expected": {
            # A/B/C totals \u2014 DRAPS returned strings that parsed to clean integers
            "A_total": a_total,
            "B_total": b_total,
            "C_total": c_total,
            "A_swap": a_swap,
            "B_swap": b_swap,
            "C_swap": c_swap,
            # SOFR path \u2014 9 quarterly points, 4-decimal precision
            "sofr_path": sofr_path,
            # Swap fixed rates from the payloads DRAPS posted to ACTUS
            "swap_now_fixed_rate": swap_now_fixed,
            "swap_later_fixed_rate": swap_later_fixed,
            # Events accumulated from response.simulation[].events
            "events_count": events_count,
            "events_digest_sha256": events_digest,
            "events": events,
        },
        "tolerances": {
            "totals_abs": 1.0,
            "swap_legs_abs": 0.01,
            "sofr_decimals": 4,
            "fixed_rate_decimals": 4,
            "_note": (
                "DRAPS returns A/B/C totals as clean integers in environmentVariables "
                "but individual leg components have float-precision noise "
                "(e.g. B_swap = 41875.00000000001). Tolerance covers that noise."
            ),
        },
    }

    # ---- Write ----
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    with FIXTURE_FILE.open("w", encoding="utf-8") as f:
        json.dump(fixture, f, indent=2, ensure_ascii=False)

    # ---- Report ----
    print()
    print(f"  \u2705 Fixture written: {FIXTURE_FILE}")
    print(f"     A_total={a_total:.0f}  B_total={b_total:.0f}  C_total={c_total:.0f}")
    print(f"     sofr_path: {len(sofr_path)} points, peak {max(p['value'] for p in sofr_path):.4f}")
    print(f"     swap_now_fixed_rate={swap_now_fixed}  swap_later_fixed_rate={swap_later_fixed}")
    print(f"     events: {events_count} cashflow events")
    print(f"     events_digest_sha256: {events_digest}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
