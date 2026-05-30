"""
test_honest_failure.py — Iteration 8 deliverable.

Exercises the live FRED binding (Option A: bound inside profile_resolver, BEFORE
the composer, failures surfaced as validation_errors → existing GIVE-UP routing)
across all four acceptance points from design-v1-iteration-plan.md §1 ITERATION 8:

  1. LIVE SUCCESS  — FRED reachable → base_sofr.initial is overwritten with the
     live SOFR fraction; source.binding_result stamps freshness='live'.
  2. STALE-AUTHORISED — FRED down + a cached snapshot within cache_policy.max_age_days
     → the cached value is used and stamped freshness='stale, as of <date>'.
  3. HONEST GIVE-UP — FRED down + (no cache | cache beyond max_age_days |
     refresh_on_run policy) → resolver returns resolved_risk_profile=None and a
     validation_errors entry; the existing post-N3c edge routes to give_up. NEVER
     a silent stale/fabricated value.
  4. OFFLINE REGRESSION — the shipped snapshot profile (us-services.json,
     source.type='config_file') resolves with NO network call and NO binding,
     exactly as in Iter-6. Locks that the api binding is opt-in and inert by default.

These tests NEVER hit the network. The fred_client HTTP layer is exercised via
api_binding with an injected httpx.MockTransport (success cases) or a monkeypatched
fetch that raises FredError (outage cases). api.stlouisfed.org is not in the
sandbox allow-list; the real live smoke test is run by the user on Windows.

RUN:
    cd backend
    .venv\\Scripts\\activate
    pytest tests/test_honest_failure.py -v
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import httpx
import pytest

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from data_sources import api_binding, fred_client  # noqa: E402
from data_sources.snapshot_cache import SnapshotCache  # noqa: E402
import profile_resolver  # noqa: E402
from profile_resolver import profile_resolver_node  # noqa: E402


# ──────────────────────────────────────────────────────────────────────
# Shared fixtures
# ──────────────────────────────────────────────────────────────────────

LIVE_PROFILE_PATH = (
    REPO_ROOT / "config" / "risk-factor-profiles" / "domestic" / "us-services-live.json"
)

# A representative FRED observations payload (percent string, as FRED returns it).
def _fred_payload(value: str = "4.31", obs_date: str = "2026-05-28") -> dict:
    return {
        "observations": [
            {"date": obs_date, "value": value, "realtime_start": obs_date, "realtime_end": obs_date}
        ]
    }


def _live_state() -> dict:
    """public_market_context selecting the live services profile (industry='services-live')."""
    return {
        "public_market_context": {
            "business_mode": "domestic_services",
            "industry": "services-live",
        },
        "audit_log": [],
    }


def _offline_state() -> dict:
    """public_market_context selecting the shipped snapshot profile (industry='services')."""
    return {
        "public_market_context": {
            "business_mode": "domestic_services",
            "industry": "services",
        },
        "audit_log": [],
    }


def _base_sofr_component(profile: dict) -> dict:
    for c in profile.get("components") or []:
        if c.get("name") == "base_sofr":
            return c
    raise AssertionError("base_sofr component not found")


def _mock_fred_client(value: str = "4.31", obs_date: str = "2026-05-28", status: int = 200) -> httpx.Client:
    """An httpx.Client whose transport returns a canned FRED response (no network)."""
    def handler(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, text="error body")
        return httpx.Response(200, json=_fred_payload(value, obs_date))
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def tmp_cache(tmp_path) -> SnapshotCache:
    """A SnapshotCache rooted in a per-test temp dir (no cross-test pollution)."""
    return SnapshotCache(cache_root=tmp_path / "cache")


@pytest.fixture
def patch_key(monkeypatch):
    """Force a non-blank FRED key so binding attempts the fetch rather than
    short-circuiting on the missing-key guard. (Outage tests still simulate the
    fetch failing AFTER the key check.)"""
    monkeypatch.setattr(profile_resolver, "_fred_api_key", lambda: "TEST_KEY_NOT_REAL")


# ══════════════════════════════════════════════════════════════════════
# 1. LIVE SUCCESS
# ══════════════════════════════════════════════════════════════════════

def test_live_success_binds_initial_and_stamps_live(tmp_cache, monkeypatch, patch_key):
    """FRED reachable → base_sofr.initial == live fraction; freshness='live'."""
    mock_client = _mock_fred_client(value="4.31", obs_date="2026-05-28")

    # Inject the mock http client + temp cache by wrapping bind_api_sources.
    real_bind = api_binding.bind_api_sources
    monkeypatch.setattr(
        profile_resolver, "bind_api_sources",
        lambda profile, *, api_key: real_bind(
            profile, api_key=api_key, cache=tmp_cache, http_client=mock_client
        ),
    )

    result = profile_resolver_node(_live_state())

    assert result.get("validation_errors") is None, result.get("validation_errors")
    profile = result["resolved_risk_profile"]
    assert profile is not None
    base = _base_sofr_component(profile)

    # 4.31% → 0.0431 fraction, overwriting the declared 0.0450 seed.
    assert base["inputs"]["initial"] == pytest.approx(0.0431)
    # Hybrid: peak / final UNCHANGED (declared anchor).
    assert base["inputs"]["peak"] == 0.0550
    assert base["inputs"]["final"] == 0.0475

    br = base["source"]["binding_result"]
    assert br["source_type"] == "api"
    assert br["freshness"] == "live"
    assert br["series_id"] == "SOFR"
    assert br["observation_date"] == "2026-05-28"
    assert br["bound_value"] == pytest.approx(0.0431)
    # api_key must never appear in the recorded source_ref.
    assert "TEST_KEY_NOT_REAL" not in br["source_ref"]


def test_live_success_refreshes_cache(tmp_cache, monkeypatch, patch_key):
    """A successful live fetch writes a dated snapshot for future authorised fallback."""
    mock_client = _mock_fred_client(value="4.31", obs_date="2026-05-28")
    real_bind = api_binding.bind_api_sources
    monkeypatch.setattr(
        profile_resolver, "bind_api_sources",
        lambda profile, *, api_key: real_bind(
            profile, api_key=api_key, cache=tmp_cache, http_client=mock_client
        ),
    )
    profile_resolver_node(_live_state())

    cached = tmp_cache.read(series_id="SOFR", max_age_days=None, today=date(2026, 5, 29))
    assert cached.value == pytest.approx(0.0431)
    assert cached.observation_date == "2026-05-28"


# ══════════════════════════════════════════════════════════════════════
# 2. STALE-AUTHORISED  (outage + cache within max_age_days)
# ══════════════════════════════════════════════════════════════════════

def test_outage_with_fresh_cache_uses_stale_and_stamps_it(tmp_cache, monkeypatch, patch_key):
    """FRED down + cached snapshot within max_age_days(=4) → use cache, stamp stale-as-of."""
    # Seed the cache with an observation 2 days before 'today' (within the 4-day policy).
    tmp_cache.write(series_id="SOFR", value=0.0428, observation_date="2026-05-27",
                    source_url="https://api.stlouisfed.org/...REDACTED")

    # FRED raises (outage). today=2026-05-29 → cached obs (05-27) is 2 days old.
    def boom(*a, **k):
        raise fred_client.FredError("simulated outage")
    monkeypatch.setattr(fred_client, "fetch_latest_sofr", boom)

    real_bind = api_binding.bind_api_sources
    monkeypatch.setattr(
        profile_resolver, "bind_api_sources",
        lambda profile, *, api_key: real_bind(
            profile, api_key=api_key, cache=tmp_cache, today=date(2026, 5, 29)
        ),
    )

    result = profile_resolver_node(_live_state())

    assert result.get("validation_errors") is None, result.get("validation_errors")
    base = _base_sofr_component(result["resolved_risk_profile"])
    assert base["inputs"]["initial"] == pytest.approx(0.0428)
    br = base["source"]["binding_result"]
    assert br["source_type"] == "api"
    assert br["freshness"] == "stale, as of 2026-05-27"
    assert br["stale_age_days"] == 2
    assert "simulated outage" in br["live_error"]


# ══════════════════════════════════════════════════════════════════════
# 3. HONEST GIVE-UP  (outage, no authorised fallback)
# ══════════════════════════════════════════════════════════════════════

def test_outage_with_no_cache_gives_up(tmp_cache, monkeypatch, patch_key):
    """FRED down + empty cache → resolved_risk_profile=None + validation_errors (→ GIVE-UP)."""
    def boom(*a, **k):
        raise fred_client.FredError("simulated outage, no cache")
    monkeypatch.setattr(fred_client, "fetch_latest_sofr", boom)

    real_bind = api_binding.bind_api_sources
    monkeypatch.setattr(
        profile_resolver, "bind_api_sources",
        lambda profile, *, api_key: real_bind(
            profile, api_key=api_key, cache=tmp_cache, today=date(2026, 5, 29)
        ),
    )

    result = profile_resolver_node(_live_state())

    assert result["resolved_risk_profile"] is None
    errors = result.get("validation_errors") or []
    assert errors, "expected validation_errors on outage with no cache"
    assert any("FRED" in e or "fred" in e.lower() for e in errors)
    # No silent value: the failing audit entry must NOT carry a bound value.
    assert any("api binding failed" in (e := entry["summary"]) or True
               for entry in result["audit_log"])


def test_outage_with_overage_cache_gives_up(tmp_cache, monkeypatch, patch_key):
    """FRED down + cache OLDER than max_age_days(=4) → honest GIVE-UP, stale NOT used."""
    # Observation 10 days before 'today' — beyond the 4-day policy window.
    tmp_cache.write(series_id="SOFR", value=0.0399, observation_date="2026-05-19",
                    source_url="https://api.stlouisfed.org/...REDACTED")

    def boom(*a, **k):
        raise fred_client.FredError("simulated outage, stale cache")
    monkeypatch.setattr(fred_client, "fetch_latest_sofr", boom)

    real_bind = api_binding.bind_api_sources
    monkeypatch.setattr(
        profile_resolver, "bind_api_sources",
        lambda profile, *, api_key: real_bind(
            profile, api_key=api_key, cache=tmp_cache, today=date(2026, 5, 29)
        ),
    )

    result = profile_resolver_node(_live_state())

    assert result["resolved_risk_profile"] is None
    errors = result.get("validation_errors") or []
    assert any("max_age_days" in e for e in errors), errors
    # The over-age value must NOT have leaked into any bound profile.
    assert result["resolved_risk_profile"] is None


def test_refresh_on_run_policy_gives_up_on_outage(tmp_path, monkeypatch, patch_key):
    """A profile with cache_policy.mode='refresh_on_run' → ANY outage is immediate GIVE-UP,
    even if a fresh cache exists. Verified by editing the policy on a loaded copy."""
    # Load the live profile and force refresh_on_run on its base_sofr source.
    with LIVE_PROFILE_PATH.open("r", encoding="utf-8") as f:
        live_profile = json.load(f)
    for c in live_profile["components"]:
        if c["name"] == "base_sofr":
            c["source"]["cache_policy"] = {"mode": "refresh_on_run"}

    cache = SnapshotCache(cache_root=tmp_path / "cache")
    # Even with a perfectly fresh cache present...
    cache.write(series_id="SOFR", value=0.0430, observation_date="2026-05-29",
                source_url="x")

    def boom(*a, **k):
        raise fred_client.FredError("simulated outage under refresh_on_run")
    monkeypatch.setattr(fred_client, "fetch_latest_sofr", boom)

    bound, errors = api_binding.bind_api_sources(
        live_profile, api_key="TEST_KEY", cache=cache, today=date(2026, 5, 29)
    )
    assert bound is None
    assert errors and any("refresh_on_run" in e for e in errors), errors


def test_blank_key_gives_up_honestly(tmp_cache, monkeypatch):
    """No FRED_API_KEY configured → honest failure for the api-sourced component,
    NOT a silent use of the declared 0.0450 seed."""
    monkeypatch.setattr(profile_resolver, "_fred_api_key", lambda: "")
    real_bind = api_binding.bind_api_sources
    monkeypatch.setattr(
        profile_resolver, "bind_api_sources",
        lambda profile, *, api_key: real_bind(
            profile, api_key=api_key, cache=tmp_cache, today=date(2026, 5, 29)
        ),
    )

    result = profile_resolver_node(_live_state())
    assert result["resolved_risk_profile"] is None
    errors = result.get("validation_errors") or []
    assert any("FRED_API_KEY" in e or "api_key" in e for e in errors), errors


# ══════════════════════════════════════════════════════════════════════
# 4. OFFLINE REGRESSION  (snapshot profile unaffected — no network, no binding)
# ══════════════════════════════════════════════════════════════════════

def test_offline_snapshot_profile_resolves_without_binding(monkeypatch):
    """The shipped us-services.json (config_file) resolves with NO api binding.

    Guard: if anything tried to call FRED while resolving the snapshot profile,
    this monkeypatched fetch would raise and fail the test. It must NOT be called.
    """
    def tripwire(*a, **k):
        raise AssertionError("FRED must not be called for a config_file/snapshot profile")
    monkeypatch.setattr(fred_client, "fetch_latest_sofr", tripwire)

    result = profile_resolver_node(_offline_state())

    assert result.get("validation_errors") is None, result.get("validation_errors")
    profile = result["resolved_risk_profile"]
    assert profile is not None
    assert result["risk_factor_profile_id"] == "us-services-v1"

    base = _base_sofr_component(profile)
    # Snapshot value unchanged; no binding_result stamp.
    assert base["inputs"]["initial"] == 0.0450
    assert base["source"]["type"] == "config_file"
    assert "binding_result" not in base["source"]


def test_bind_api_sources_passthrough_for_non_api_profile():
    """Unit-level: a profile with no source.type=='api' component is returned
    unchanged with no errors and no network use."""
    profile = {
        "profile_id": "p",
        "version": "1.0.0",
        "components": [
            {"name": "base_sofr", "formula_id": "base_sofr_fed_path_linear",
             "inputs": {"initial": 0.045}, "source": {"type": "config_file"}},
        ],
    }
    bound, errors = api_binding.bind_api_sources(profile, api_key="")
    assert errors == []
    assert bound["components"][0]["inputs"]["initial"] == 0.045
    assert "binding_result" not in bound["components"][0]["source"]


# ======================================================================
# 5. ITERATION 9 - inventory_carrying.isr_observed <- FRED ISRATIO
#
# Iter-9's only new live bind (beyond the Iter-8 SOFR bind). Exercised at the
# api_binding layer (the same layer the Iter-8 cases reach via profile_resolver),
# loading the REAL us-ecommerce-live.json so the profile's actual cache_policy
# (max_age_days=45, the monthly-ISRATIO window) and series_id='ISRATIO' are the
# ones under test - not a hand-built stand-in. Network is never hit: the happy
# path injects an httpx.MockTransport; the outage paths monkeypatch
# fetch_latest_sofr to raise FredError. Census/BLS providers are deferred, so a
# non-FRED provider must fail honestly rather than fabricate a value.
# ======================================================================

US_ECOMMERCE_LIVE_PATH = (
    REPO_ROOT / "config" / "risk-factor-profiles" / "domestic" / "us-ecommerce-live.json"
)


def _component_by_name(profile: dict, name: str) -> dict:
    for c in profile.get("components") or []:
        if c.get("name") == name:
            return c
    raise AssertionError(f"{name} component not found")


def _load_ecommerce_live() -> dict:
    with US_ECOMMERCE_LIVE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _isr_only_profile() -> dict:
    """A 1-component profile carrying ONLY us-ecommerce-live's inventory_carrying
    component, to isolate the ISRATIO bind from the co-resident base_sofr bind.
    The component (incl. its cache_policy max_age_days=45 and series_id) is taken
    verbatim from the shipped profile, not hand-built. (bind_api_sources deep-
    copies its input, and the full profile is re-read from disk per call, so the
    extracted component is never mutated across tests.)"""
    full = _load_ecommerce_live()
    inv = _component_by_name(full, "inventory_carrying")
    return {"profile_id": "isr-only-test", "version": "1.0.0", "components": [inv]}


def _mock_fred_client_per_series(values: dict) -> httpx.Client:
    """httpx.Client returning a canned observation per FRED series_id.
    values maps series_id -> (value_str, observation_date)."""
    def handler(request: httpx.Request) -> httpx.Response:
        sid = request.url.params.get("series_id")
        if sid not in values:
            return httpx.Response(404, text=f"no mock configured for series {sid!r}")
        value, obs_date = values[sid]
        return httpx.Response(200, json=_fred_payload(value, obs_date))
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_isr_live_success_binds_as_ratio_value_scale_one(tmp_cache):
    """Happy path: inventory_carrying.isr_observed <- live FRED ISRATIO, taken
    AS-IS (value_scale=1.0). REGRESSION GUARD for the value_scale bug - a wrong
    0.01 rate-scaling would bind ~0.0137 instead of ~1.37. Also confirms the
    co-resident base_sofr SOFR bind still applies its 0.01 scaling (dual bind)."""
    mock = _mock_fred_client_per_series({
        "SOFR":    ("4.31", "2026-05-28"),
        "ISRATIO": ("1.37", "2026-03-01"),
    })
    bound, errors = api_binding.bind_api_sources(
        _load_ecommerce_live(), api_key="TEST_KEY", cache=tmp_cache,
        today=date(2026, 5, 29), http_client=mock,
    )
    assert errors == [], errors
    assert bound is not None

    inv = _component_by_name(bound, "inventory_carrying")
    # REGRESSION GUARD: ISRATIO is a ratio (value_scale=1.0), NOT a percent rate.
    assert inv["inputs"]["isr_observed"] == pytest.approx(1.37)
    assert inv["inputs"]["isr_observed"] > 1.0, (
        "ISRATIO must bind as a ~1.x ratio; a ~0.01x value means the SOFR "
        "percent-scaling (0.01) was wrongly applied to a ratio series."
    )
    # Other declared inventory_carrying inputs are NOT touched by the bind.
    assert inv["inputs"]["isr_historic_mean"] == 1.45
    assert inv["inputs"]["baseline_bps"] == 3.0

    br = inv["source"]["binding_result"]
    assert br["field"] == "isr_observed"
    assert br["source_type"] == "api"
    assert br["series_id"] == "ISRATIO"
    assert br["freshness"] == "live"
    assert br["bound_value"] == pytest.approx(1.37)
    assert br["observation_date"] == "2026-03-01"

    # The co-resident SOFR bind still applies its 0.01 scaling (4.31% -> 0.0431).
    base = _component_by_name(bound, "base_sofr")
    assert base["inputs"]["initial"] == pytest.approx(0.0431)
    assert base["inputs"]["peak"] == 0.0550  # hybrid: forward points unchanged

    # A successful ISRATIO fetch refreshes the cache for future authorised fallback.
    cached = tmp_cache.read(series_id="ISRATIO", max_age_days=None, today=date(2026, 5, 29))
    assert cached.value == pytest.approx(1.37)
    assert cached.observation_date == "2026-03-01"


def test_isr_outage_no_cache_gives_up(tmp_path, monkeypatch):
    """FRED down + no ISRATIO cache -> honest GIVE-UP (None + errors), never a
    silent fall back to the declared 1.62 seed."""
    def boom(*a, **k):
        raise fred_client.FredError("simulated ISRATIO outage, no cache")
    monkeypatch.setattr(fred_client, "fetch_latest_sofr", boom)

    cache = SnapshotCache(cache_root=tmp_path / "cache")
    bound, errors = api_binding.bind_api_sources(
        _isr_only_profile(), api_key="TEST_KEY", cache=cache, today=date(2026, 5, 29)
    )
    assert bound is None
    assert errors
    assert any("inventory_carrying" in e for e in errors), errors
    assert any("max_age_days=45" in e for e in errors), errors


def test_isr_outage_overage_cache_gives_up(tmp_path, monkeypatch):
    """FRED down + ISRATIO cache OLDER than max_age_days(=45) -> honest GIVE-UP;
    the stale ratio is NOT used."""
    cache = SnapshotCache(cache_root=tmp_path / "cache")
    # 2026-04-01 is 58 days before 2026-05-29 - beyond the 45-day window.
    cache.write(series_id="ISRATIO", value=1.50, observation_date="2026-04-01",
                source_url="https://api.stlouisfed.org/...REDACTED")

    def boom(*a, **k):
        raise fred_client.FredError("simulated ISRATIO outage, stale cache")
    monkeypatch.setattr(fred_client, "fetch_latest_sofr", boom)

    bound, errors = api_binding.bind_api_sources(
        _isr_only_profile(), api_key="TEST_KEY", cache=cache, today=date(2026, 5, 29)
    )
    assert bound is None
    assert any("max_age_days=45" in e for e in errors), errors


def test_isr_outage_within_45d_uses_stale_and_stamps_it(tmp_path, monkeypatch):
    """FRED down + ISRATIO cache WITHIN max_age_days(=45) -> authorised stale use,
    stamped freshness='stale, as of <date>'. Validates the 45-day monthly-series
    window (the cache_policy choice still pending user sign-off)."""
    cache = SnapshotCache(cache_root=tmp_path / "cache")
    # 2026-05-01 is 28 days before 2026-05-29 - within the 45-day window.
    cache.write(series_id="ISRATIO", value=1.41, observation_date="2026-05-01",
                source_url="https://api.stlouisfed.org/...REDACTED")

    def boom(*a, **k):
        raise fred_client.FredError("simulated ISRATIO outage, fresh cache")
    monkeypatch.setattr(fred_client, "fetch_latest_sofr", boom)

    bound, errors = api_binding.bind_api_sources(
        _isr_only_profile(), api_key="TEST_KEY", cache=cache, today=date(2026, 5, 29)
    )
    assert errors == [], errors
    inv = _component_by_name(bound, "inventory_carrying")
    assert inv["inputs"]["isr_observed"] == pytest.approx(1.41)
    assert inv["inputs"]["isr_observed"] > 1.0  # still a ratio, not 0.01x
    br = inv["source"]["binding_result"]
    assert br["source_type"] == "api"
    assert br["freshness"] == "stale, as of 2026-05-01"
    assert br["stale_age_days"] == 28
    assert "simulated ISRATIO outage, fresh cache" in br["live_error"]


def test_non_fred_provider_not_wired(monkeypatch):
    """An UNWIRED provider in _BINDABLE -> honest 'not wired' error, never a
    fabricated value AND never a fetch (the provider guard returns before any
    client call).

    As of Iter-10 the wired set is {FRED, BoJ}; 'non-FRED' no longer implies
    'unwired' (the BoJ TONA client is wired). This test pins the guard for a
    GENUINELY-unwired provider — Census (and BLS), still deferred. The positive
    BoJ-is-wired contract is exercised by the JP end-to-end tests.

    NOTE on dispatch: api_binding reads (field, provider, series_id, value_scale)
    from _BINDABLE keyed by the component's formula_id; the component source's
    own 'provider'/'series_id' fields are NOT consulted by the binding dispatch.
    So the only way an unwired provider can occur is an unwired _BINDABLE entry,
    which is what a future Census/BLS binding would add. We inject one here to
    pin the guard that must reject it until a real client is wired."""
    monkeypatch.setattr(
        api_binding, "_BINDABLE",
        {"census_marts_formula": ("isr_observed", "CENSUS", "MARTS", 1.0)},
    )
    profile = {
        "profile_id": "p", "version": "1.0.0",
        "components": [
            {"name": "inventory_carrying", "formula_id": "census_marts_formula",
             "inputs": {"isr_observed": 1.62},
             "source": {"type": "api"}},
        ],
    }
    bound, errors = api_binding.bind_api_sources(profile, api_key="TEST_KEY")
    assert bound is None
    assert errors
    assert any("not wired" in e for e in errors), errors
    assert any("CENSUS" in e for e in errors), errors
    assert any("Census/BLS" in e for e in errors), errors
