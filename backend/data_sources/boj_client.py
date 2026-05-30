"""
data_sources/boj_client.py — Bank of Japan (BoJ) TONA client.

Iteration 10 deliverable. Binds the base_sofr component's `initial` input to the
latest TONA (Tokyo Overnight Average Rate) observation from the BoJ Time-Series
Data Search (stat-search).

CONTRACT MIRRORS fred_client.py, with two deliberate differences:
  1. BoJ stat-search serves a CSV *download*, NOT a JSON REST API.
  2. There is NO api_key — BoJ stat-search is open (no registered key).

HONEST-FAILURE CONTRACT (identical philosophy to fred_client.py;
design-v1-free-apis.md §8 item 4; iteration-plan §0):
    Every failure path RAISES BojError. There is NO silent fallback to a
    hardcoded or simulated rate. The caller (api_binding) decides whether a
    cached snapshot may substitute, per the profile's cache_policy — that
    decision lives in api_binding, never here.

Failure modes that raise:
    - any required BoJ access detail is still an un-smoked placeholder (see below)
    - network error / timeout
    - non-200 HTTP status
    - CSV undecodable in the declared encoding
    - no parseable data rows
    - BoJ "value not available" sentinel
    - value not parseable as a finite rate
    - latest row missing a usable date

⚠️  PENDING USER WINDOWS-SIDE SMOKE — Rule 2 (NOT fabricated here)
    The concrete BoJ access details are NOT verifiable from the build sandbox:
    www.stat-search.boj.or.jp is not on the allow-list and the filesystem MCP
    cannot issue HTTP. The following are therefore PLACEHOLDERS:
        BOJ_TONA_DOWNLOAD_URL  — the verified CSV-download URL
        TONA_SERIES_ID         — the verified BoJ series code for TONA
        _CSV_HEADER_ROWS       — leading non-data rows to skip
        _CSV_DATE_COL          — 0-based column index of the observation date
        _CSV_VALUE_COL         — 0-based column index of the TONA rate (percent)
        _CSV_ENCODING          — BoJ CSVs are commonly Shift-JIS/cp932 (UNCONFIRMED)
    Until the user runs the live smoke on their Windows host and fills these in,
    fetch_latest_tona RAISES BojError on the live path rather than guessing.
    Exact precedent: Iter-8 shipped us-services-live with the FRED smoke owed.

    The OFFLINE jp-services.json profile (pinned TONA snapshot, source.type=
    config_file) never reaches this module and is fully CI-testable now. The
    offline TESTS for this module inject a mock client + explicit access details
    (so the parse logic is exercised deterministically without the network and
    without depending on the still-unknown live constants).

    BoJ stat-search root: https://www.stat-search.boj.or.jp/

ALSO PENDING SMOKE (structural assumptions to confirm against a real CSV):
    - "latest = last data row" assumes BoJ returns ascending-by-date. If the
      download is descending, set _LATEST_IS_LAST = False after smoke.
    - the missing-value sentinel set (_BOJ_MISSING_SENTINELS) is a best-guess
      union of common conventions; confirm BoJ's actual sentinel on smoke.
    - whether the download is GET vs POST and whether special headers are
      required; this client issues a GET (adjust after smoke if needed).

NO LLM IMPORTS — deterministic by design (agent-type law).
"""

from __future__ import annotations

from dataclasses import dataclass
import csv as _csv
import io as _io

import httpx

# TONA is published as a PERCENT (e.g. "0.477" == 0.477%). The base_sofr
# component expects a DECIMAL FRACTION (0.00477) — same convention as SOFR.
# Conversion happens here so the pipeline sees the fraction convention used by
# every component formula. (Same _PERCENT_TO_FRACTION semantics as fred_client.)
_PERCENT_TO_FRACTION = 0.01

DEFAULT_TIMEOUT_SECONDS = 8.0

# ----------------------------------------------------------------------------
# ⚠️  PLACEHOLDERS — PENDING USER SMOKE. Do NOT trust these values.
#     fetch_latest_tona() raises BojError on the live path while any of these
#     is still unset, so a wrong rate can never be emitted silently.
# ----------------------------------------------------------------------------
_PLACEHOLDER_URL = "__PENDING_BOJ_SMOKE_URL__"
_PLACEHOLDER_SERIES = "__PENDING_BOJ_SMOKE_SERIES_ID__"

BOJ_TONA_DOWNLOAD_URL: str = _PLACEHOLDER_URL   # verified CSV-download URL goes here
TONA_SERIES_ID: str = _PLACEHOLDER_SERIES       # verified BoJ TONA series code goes here

# CSV layout (0-based indices). None == unverified -> live path raises.
_CSV_HEADER_ROWS: int | None = None             # leading non-data rows to skip
_CSV_DATE_COL: int | None = None                # column holding observation date
_CSV_VALUE_COL: int | None = None               # column holding TONA rate (percent)
_CSV_ENCODING: str | None = None                # e.g. "shift_jis" / "cp932" — UNCONFIRMED

# Structural assumptions (confirm on smoke).
_LATEST_IS_LAST = True                           # True if rows are ascending-by-date
_BOJ_MISSING_SENTINELS = frozenset({"", "ND", "NA", "N/A", "*", "-", "--", "."})


class BojError(RuntimeError):
    """Raised on ANY BoJ TONA fetch failure. Never silently swallowed.

    The caller may catch this to decide on a profile-authorised cache fallback,
    but this client itself never substitutes a value. (Mirror of FredError.)
    """


@dataclass(frozen=True)
class TonaObservation:
    """One TONA observation, normalised to the component fraction convention.

    Field-for-field mirror of fred_client.SofrObservation so api_binding can
    construct its binding_result uniformly across providers.

    Attributes:
      value:            the observation scaled by value_scale. TONA passes
                        value_scale=0.01 -> a decimal FRACTION (0.00477 for
                        0.477%).
      observation_date: the BoJ observation date as it appears in the CSV — the
                        date the rate is *for*, not the fetch time. Stamped as
                        the data's "as of" date. (Format is BoJ-native until the
                        smoke confirms it; not reformatted here to avoid guessing.)
      series_id:        the BoJ series queried.
      source_url:       the download URL. BoJ stat-search uses no api_key, so
                        there is no secret to redact (unlike FRED).
    """

    value: float
    observation_date: str
    series_id: str
    source_url: str


def _require_smoked(
    *, download_url: str, series_id: str,
    header_rows: int | None, date_col: int | None,
    value_col: int | None, encoding: str | None,
) -> None:
    """Raise BojError if any access detail is still an un-smoked placeholder.

    This is the honest-failure gate for the live path: until the user runs the
    Windows-side smoke and supplies verified values, the client refuses to fetch
    rather than guess a URL/series/layout. Offline tests bypass this by passing
    every detail explicitly.
    """
    unset = []
    if not download_url or download_url == _PLACEHOLDER_URL:
        unset.append("download_url (BOJ_TONA_DOWNLOAD_URL)")
    if not series_id or series_id == _PLACEHOLDER_SERIES:
        unset.append("series_id (TONA_SERIES_ID)")
    if header_rows is None:
        unset.append("header_rows (_CSV_HEADER_ROWS)")
    if date_col is None:
        unset.append("date_col (_CSV_DATE_COL)")
    if value_col is None:
        unset.append("value_col (_CSV_VALUE_COL)")
    if not encoding:
        unset.append("encoding (_CSV_ENCODING)")
    if unset:
        raise BojError(
            "BoJ TONA access details are not yet verified (pending Windows-side "
            "smoke against https://www.stat-search.boj.or.jp/). Unset: "
            + "; ".join(unset)
            + ". Refusing to fabricate a URL/series/CSV-layout. Run the smoke, "
            "fill in the boj_client placeholders (or pass them explicitly), then "
            "retry. The offline jp-services.json (config_file TONA snapshot) does "
            "not require this and is usable now."
        )


def _parse_latest_tona_csv(
    csv_text: str, *, header_rows: int, date_col: int, value_col: int, series_id: str,
) -> tuple[str, float]:
    """Parse the BoJ CSV text and return (observation_date, raw_percent_value).

    Honest-failure: raises BojError on no data, sentinel-only, or unparseable
    value. Does NOT scale the value (caller applies value_scale).
    """
    rows = list(_csv.reader(_io.StringIO(csv_text)))
    data_rows = rows[header_rows:]

    candidates: list[tuple[str, str]] = []  # (date_raw, value_raw)
    for row in data_rows:
        if len(row) <= max(date_col, value_col):
            continue
        value_raw = (row[value_col] or "").strip()
        date_raw = (row[date_col] or "").strip()
        if value_raw in _BOJ_MISSING_SENTINELS:
            continue
        if not date_raw:
            continue
        candidates.append((date_raw, value_raw))

    if not candidates:
        raise BojError(
            f"BoJ CSV for series {series_id!r} contained no parseable data rows "
            f"(header_rows={header_rows}, date_col={date_col}, value_col={value_col}); "
            "every candidate was empty or a missing-value sentinel. Refusing to "
            "fabricate a value. Verify the CSV layout against a real download."
        )

    date_raw, value_raw = candidates[-1] if _LATEST_IS_LAST else candidates[0]

    try:
        raw_number = float(value_raw)
    except (TypeError, ValueError) as exc:
        raise BojError(
            f"BoJ latest TONA value {value_raw!r} for series {series_id!r} "
            f"(date={date_raw!r}) is not parseable as a number: {exc}."
        ) from exc

    return date_raw, raw_number


def fetch_latest_tona(
    *,
    series_id: str = TONA_SERIES_ID,
    value_scale: float = _PERCENT_TO_FRACTION,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    download_url: str | None = None,
    header_rows: int | None = None,
    date_col: int | None = None,
    value_col: int | None = None,
    encoding: str | None = None,
    client: httpx.Client | None = None,
) -> TonaObservation:
    """Fetch the most recent TONA observation from BoJ stat-search.

    Mirrors fred_client.fetch_latest_sofr but takes NO api_key (BoJ is open) and
    parses a CSV download instead of JSON.

    Every access detail defaults to the module-level placeholder/constant. On
    the LIVE path those placeholders cause an honest BojError (see _require_smoked)
    until the user supplies smoke-verified values. Offline tests pass each detail
    explicitly together with a mock `client`, exercising the parse path
    deterministically without the network.

    Args:
      series_id:      BoJ series code for TONA (placeholder until smoked).
      value_scale:    multiplier on the raw CSV value. Defaults to 0.01
                      (percent -> decimal fraction, the TONA/SOFR convention).
      timeout_seconds: per-request timeout.
      download_url:   override the module BOJ_TONA_DOWNLOAD_URL.
      header_rows / date_col / value_col / encoding: CSV layout overrides.
      client:         optional pre-built httpx.Client (tests inject a transport).

    Returns:
      TonaObservation with value as a decimal fraction.

    Raises:
      BojError on any failure. Never returns a fabricated value.
    """
    eff_url = download_url if download_url is not None else BOJ_TONA_DOWNLOAD_URL
    eff_series = series_id
    eff_header_rows = header_rows if header_rows is not None else _CSV_HEADER_ROWS
    eff_date_col = date_col if date_col is not None else _CSV_DATE_COL
    eff_value_col = value_col if value_col is not None else _CSV_VALUE_COL
    eff_encoding = encoding if encoding is not None else _CSV_ENCODING

    _require_smoked(
        download_url=eff_url, series_id=eff_series,
        header_rows=eff_header_rows, date_col=eff_date_col,
        value_col=eff_value_col, encoding=eff_encoding,
    )

    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=timeout_seconds)

    try:
        try:
            resp = client.get(eff_url)
        except httpx.HTTPError as exc:
            raise BojError(
                f"BoJ request failed at the transport layer for series "
                f"{eff_series!r} (url={eff_url}): {type(exc).__name__}: {exc}. "
                "No fallback — the caller decides whether a profile-authorised "
                "cache may substitute."
            ) from exc

        if resp.status_code != 200:
            raise BojError(
                f"BoJ returned HTTP {resp.status_code} for series {eff_series!r} "
                f"(url={eff_url}). Body[:200]={resp.text[:200]!r}."
            )

        try:
            csv_text = resp.content.decode(eff_encoding)
        except (LookupError, UnicodeDecodeError) as exc:
            raise BojError(
                f"BoJ CSV for series {eff_series!r} could not be decoded with "
                f"encoding {eff_encoding!r} (url={eff_url}): {exc}. Confirm the "
                "BoJ download encoding on smoke (commonly Shift-JIS/cp932)."
            ) from exc

        obs_date, raw_number = _parse_latest_tona_csv(
            csv_text,
            header_rows=eff_header_rows,
            date_col=eff_date_col,
            value_col=eff_value_col,
            series_id=eff_series,
        )

        return TonaObservation(
            value=raw_number * value_scale,
            observation_date=obs_date,
            series_id=eff_series,
            source_url=eff_url,
        )
    finally:
        if owns_client:
            client.close()
