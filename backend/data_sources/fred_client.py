"""
data_sources/fred_client.py — FRED (Federal Reserve Economic Data) client.

Iteration 8 deliverable. Binds the base_sofr component's `initial` input to the
latest SOFR observation from FRED.

API (per design-v1-free-apis.md §1):
    GET https://api.stlouisfed.org/fred/series/observations
        ?series_id=SOFR
        &api_key=<32-char key>
        &file_type=json
        &sort_order=desc
        &limit=1
    → {"observations": [{"date": "YYYY-MM-DD", "value": "4.31", ...}]}

HONEST-FAILURE CONTRACT (design-v1-free-apis.md §8 item 4; iteration-plan §0):
    Every failure path RAISES FredError. There is NO silent fallback to a
    hardcoded or simulated rate. The caller (api_binding) decides whether a
    cached snapshot may substitute, per the profile's cache_policy — that
    decision lives in api_binding, never here.

Failure modes that raise:
    - no api key configured
    - network error / timeout
    - non-200 HTTP status
    - malformed JSON / missing observations
    - FRED's "value not available" sentinel ("." per FRED convention)
    - value not parseable as a finite rate

NO LLM IMPORTS — deterministic by design (agent-type law).
NOTE: api.stlouisfed.org is NOT in the sandbox allowed-domains list; the live
smoke test runs on the user's Windows host. The offline tests
(test_honest_failure.py) monkeypatch the HTTP layer and never hit the network.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

# FRED returns rates as PERCENT (e.g. "4.31" == 4.31%). The base_sofr component's
# inputs_schema expects a DECIMAL FRACTION (0.0431) in [-0.05, 0.30]. Conversion
# happens here so the rest of the pipeline sees the fraction convention used by
# every component formula (see components/_common.py units note).
_PERCENT_TO_FRACTION = 0.01

# FRED's documented sentinel for a missing observation.
_FRED_MISSING_SENTINEL = "."

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
DEFAULT_TIMEOUT_SECONDS = 8.0


class FredError(RuntimeError):
    """Raised on ANY FRED fetch failure. Never silently swallowed.

    The caller may catch this to decide on a profile-authorised cache fallback,
    but this client itself never substitutes a value.
    """


@dataclass(frozen=True)
class SofrObservation:
    """One SOFR observation, normalised to the component fraction convention.

    Attributes:
      value:        the observation scaled by the caller's value_scale. Rate
                    series (SOFR) pass value_scale=0.01 -> a decimal FRACTION
                    (0.0431 for 4.31%). Ratio series (ISRATIO) pass
                    value_scale=1.0 -> the raw ratio (e.g. 1.45) taken AS-IS.
      observation_date: the FRED observation date (YYYY-MM-DD) — the date the
                    rate is *for*, not the fetch time. This is what gets stamped
                    as the data's "as of" date.
      series_id:    the FRED series queried (e.g. "SOFR").
      source_url:   the request URL WITHOUT the api_key (keys must never appear
                    in logs, provenance, or URLs — see user_privacy rules).
    """

    value: float
    observation_date: str
    series_id: str
    source_url: str


def _redact_key(url: str) -> str:
    """Strip api_key from a URL so it never lands in provenance/logs."""
    if "api_key=" not in url:
        return url
    parts = []
    for seg in url.split("&"):
        if seg.startswith("api_key=") or "?api_key=" in seg:
            # Keep the query-prefix if api_key was the first param.
            if "?api_key=" in seg:
                parts.append(seg.split("?api_key=")[0] + "?api_key=REDACTED")
            else:
                parts.append("api_key=REDACTED")
        else:
            parts.append(seg)
    return "&".join(parts)


def fetch_latest_sofr(
    api_key: str,
    *,
    series_id: str = "SOFR",
    value_scale: float = _PERCENT_TO_FRACTION,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    client: httpx.Client | None = None,
) -> SofrObservation:
    """Fetch the most recent SOFR observation from FRED.

    Args:
      api_key: FRED 32-char key. If blank/None → FredError (no anonymous access).
      series_id: FRED series; defaults to "SOFR".
      value_scale: multiplier applied to the raw FRED value. Defaults to 0.01
                   (percent rate -> decimal fraction, the SOFR convention).
                   Pass 1.0 for series already in the units the component
                   expects (e.g. ISRATIO, a ratio). NEVER blindly 0.01 a
                   non-percent series.
      timeout_seconds: per-request timeout.
      client: optional pre-built httpx.Client (tests inject a transport here).

    Returns:
      SofrObservation with value as a decimal fraction.

    Raises:
      FredError on any failure. Never returns a fabricated value.
    """
    if not api_key or not api_key.strip():
        raise FredError(
            "FRED api_key is not configured (FRED_API_KEY blank). FRED requires a "
            "free registered key; anonymous access is not available. Set FRED_API_KEY "
            "in the backend .env to enable live binding, or use a config_file/snapshot "
            "profile for offline runs."
        )

    params = {
        "series_id": series_id,
        "api_key": api_key.strip(),
        "file_type": "json",
        "sort_order": "desc",
        "limit": "1",
    }

    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=timeout_seconds)

    try:
        try:
            resp = client.get(FRED_BASE_URL, params=params)
        except httpx.HTTPError as exc:
            # Network error, timeout, DNS failure, connection refused, etc.
            raise FredError(
                f"FRED request failed at the transport layer for series "
                f"{series_id!r}: {type(exc).__name__}: {exc}. No fallback — the "
                "caller decides whether a profile-authorised cache may substitute."
            ) from exc

        redacted = _redact_key(str(resp.request.url))

        if resp.status_code != 200:
            raise FredError(
                f"FRED returned HTTP {resp.status_code} for series {series_id!r} "
                f"(url={redacted}). Body[:200]={resp.text[:200]!r}."
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise FredError(
                f"FRED response for series {series_id!r} was not valid JSON "
                f"(url={redacted}): {exc}."
            ) from exc

        observations = data.get("observations")
        if not isinstance(observations, list) or not observations:
            raise FredError(
                f"FRED response for series {series_id!r} had no observations "
                f"(url={redacted}); payload keys={sorted(data) if isinstance(data, dict) else type(data).__name__}."
            )

        obs = observations[0]
        raw_value = obs.get("value")
        obs_date = obs.get("date")

        if raw_value is None or raw_value == _FRED_MISSING_SENTINEL:
            raise FredError(
                f"FRED latest observation for series {series_id!r} is the "
                f"missing-value sentinel {raw_value!r} (date={obs_date!r}). FRED has "
                "no published value yet; refusing to fabricate one."
            )

        try:
            raw_number = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise FredError(
                f"FRED latest observation value {raw_value!r} for series "
                f"{series_id!r} is not parseable as a number: {exc}."
            ) from exc

        if not isinstance(obs_date, str) or not obs_date.strip():
            raise FredError(
                f"FRED latest observation for series {series_id!r} has no usable "
                f"'date' field (got {obs_date!r}); cannot stamp an 'as of' date."
            )

        scaled_value = raw_number * value_scale

        return SofrObservation(
            value=scaled_value,
            observation_date=obs_date.strip(),
            series_id=series_id,
            source_url=redacted,
        )
    finally:
        if owns_client:
            client.close()
