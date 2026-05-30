"""
data_sources/api_binding.py — resolve source.type=="api" component inputs to
live values, with profile-authorised cache fallback. (Iteration 8.)

WHERE THIS RUNS
===============
Called by profile_resolver_node (N3a) AFTER the layered deep-merge produces the
resolved profile, and BEFORE the composer (N3d). This keeps graph.py and
composer.py wiring UNCHANGED (Option A): the binding is part of "resolving" the
profile, and any failure is surfaced as validation_errors, which the EXISTING
post-N3c conditional edge (route_after_profile_spec_validator) routes to
give_up. No new node, no new edge.

WHAT IT BINDS (Iteration 8 + 9 + 10 scope)
=====================================
Only the base_sofr component's `initial` input, only when that component's
`source.type == "api"`. This is the HYBRID transform agreed for Iter-8:
  - `initial`         ← live FRED SOFR latest observation
  - `peak` / `final`  ← stay profile-declared (a Fed dot-plot source for the
                        forward points is a later iteration).
Iteration 9 adds inventory_carrying's `isr_observed` ← live FRED ISRATIO (the
monthly retailers' inventory-to-sales ratio, bound AS-IS with value_scale=1.0,
NOT the 0.01 rate scaling). Iteration 10 adds the BoJ TONA bind for the JP
profile's base_sofr.initial (provider='BoJ', value_scale=0.01, NO api_key; see
boj_client.py — live URL/series/CSV-layout pending user smoke). Census M3/MRTS
and BLS clients are deferred (no
verified Census query shape from the sandbox; no Iter-9 BLS consumer). The
provider dispatch in _bind_one_component (FRED + BoJ wired as of Iter-10)
rejects any unwired provider rather than guessing a value.
Components whose source.type != "api" (the snapshot-backed config_file
components in Iter-6/7 profiles) are left untouched — offline/CI runs never
reach the network.

CACHE POLICY (per profile, lives inside component.source.cache_policy)
======================================================================
Schema-legal because the profile schema's component `source` is a free-form
object (no additionalProperties:false), so cache_policy needs NO schema change.

  source.cache_policy = {
    "mode": "refresh_on_run" | "cached_within_days",
    "max_age_days": <int>            # required iff mode == "cached_within_days"
  }

Behaviour:
  mode == "refresh_on_run" (default if cache_policy absent):
      live fetch REQUIRED. On any FredError → honest failure (validation_errors
      → GIVE-UP). Never substitutes stale data. On success, the snapshot cache
      is refreshed for future authorised fallbacks.
  mode == "cached_within_days":
      try live first; on success refresh cache + use live. On FredError, read
      the most recent cached snapshot; if within max_age_days, USE IT and stamp
      freshness="stale, as of <observation_date>". If no usable snapshot →
      honest failure.

PROVENANCE
==========
The binding result is written into the component's free-form
`source.binding_result` block (travels with resolved_risk_profile to the
composer and the provenance node) AND summarised in the resolver's audit_log
entry. Shape:
    source.binding_result = {
      "field": "initial",
      "bound_value": 0.0431,
      "source_type": "api",                # provenance.SOURCE_TYPE_API
      "series_id": "SOFR",
      "source_ref": "<FRED url, key redacted>" | "<cache file>",
      "observation_date": "2026-05-20",
      "freshness": "live" | "stale, as of 2026-05-20",
      "fetched_at": "<iso8601 utc>"
    }
NOTE: this iteration records api provenance AT THE BINDING SITE. Folding the
api source_type into N6a's per-SOFR-point report is deferred together with the
per-(point,component) attribution work flagged in PROJECT_CONTEXT.md §7 (N6a's
v2_direct per-point stamping is a draps_v1-shaped stopgap). The binding_result
block is the authoritative api attribution until that lands.

HONEST-FAILURE RETURN CONTRACT
==============================
bind_api_sources returns (bound_profile, errors):
  - errors == []  → bound_profile is a NEW dict with api inputs filled in.
  - errors != []  → bound_profile is None; the resolver surfaces errors as
                    validation_errors and routes to GIVE-UP. NEVER a silent
                    derived run on an unbound/ stale-but-unauthorised value.

NO LLM IMPORTS — deterministic by design (agent-type law).
"""

from __future__ import annotations

import copy
from datetime import date, datetime, timezone
from typing import Any

from . import boj_client, fred_client
from .snapshot_cache import CacheMiss, SnapshotCache

# Provenance source-type constant. Imported lazily inside functions would be
# cleaner for cycles, but provenance.py has no import of this module, so a
# top-level import is safe. Kept as a literal mirror to avoid a hard dependency
# on backend/ being importable from the data_sources package in every context.
SOURCE_TYPE_API = "api"

# (component formula_id) -> (input field, provider, series_id, value_scale).
# Iter-8 bound base_sofr only. Iter-9 adds inventory_carrying's isr_observed
# (FRED ISRATIO — a MONTHLY RATIO, so value_scale=1.0; applying the 0.01 rate
# scaling here would bind 0.0145 instead of 1.45). value_scale is forwarded to
# the FRED client so a ratio series is taken as-is and a percent rate (SOFR) is
# converted to a fraction.
_BINDABLE = {
    "base_sofr_fed_path_linear":  ("initial",      "FRED", "SOFR",    0.01),
    "inventory_carrying_dso_dpo": ("isr_observed", "FRED", "ISRATIO", 1.0),
    # Iter-10: BoJ TONA -> base_sofr.initial for the JP (jp-services-live) profile.
    # value_scale=0.01 (TONA is a percent rate, same convention as SOFR). The
    # series_id is sourced from boj_client.TONA_SERIES_ID — a PLACEHOLDER pending
    # the user's Windows-side smoke. boj_client.fetch_latest_tona raises BojError
    # on the live path until the smoke values are filled in, so no wrong rate can
    # bind. See boj_client.py for the smoke checklist.
    "base_sofr_boj_path_linear":  ("initial",      "BoJ",  boj_client.TONA_SERIES_ID, 0.01),
}

# Providers with a wired client. A formula_id mapped to any other provider gets
# an honest "not wired" error rather than a fabricated value (Census/BLS deferred).
_WIRED_PROVIDERS = frozenset({"FRED", "BoJ"})

_VALID_CACHE_MODES = frozenset({"refresh_on_run", "cached_within_days"})


class ApiBindingError(RuntimeError):
    """Internal-shape error in a cache_policy or binding spec (a config defect,
    distinct from a live-data outage). Surfaced to the caller as an error
    string, never silently ignored."""


def _parse_cache_policy(source: dict, component_name: str) -> tuple[str, int | None, list[str]]:
    """Return (mode, max_age_days, errors). Default mode is refresh_on_run."""
    errors: list[str] = []
    policy = source.get("cache_policy")
    if policy is None:
        return "refresh_on_run", None, errors
    if not isinstance(policy, dict):
        errors.append(
            f"component '{component_name}': source.cache_policy must be an object, "
            f"got {type(policy).__name__}."
        )
        return "refresh_on_run", None, errors

    mode = policy.get("mode", "refresh_on_run")
    if mode not in _VALID_CACHE_MODES:
        errors.append(
            f"component '{component_name}': source.cache_policy.mode={mode!r} invalid; "
            f"expected one of {sorted(_VALID_CACHE_MODES)}."
        )
        return "refresh_on_run", None, errors

    max_age_days: int | None = None
    if mode == "cached_within_days":
        raw = policy.get("max_age_days")
        if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
            errors.append(
                f"component '{component_name}': source.cache_policy.mode="
                f"'cached_within_days' requires integer max_age_days >= 0; got {raw!r}."
            )
        else:
            max_age_days = raw
    return mode, max_age_days, errors


def _fetch_live_observation(
    provider: str,
    *,
    api_key: str,
    series_id: str,
    value_scale: float,
    http_client: Any | None,
):
    """Dispatch a live fetch to the provider's client.

    Returns an observation object exposing .value/.observation_date/.series_id/
    .source_url (uniform across providers), or raises that provider's *Error.
    FRED takes an api_key; BoJ stat-search is open and takes NONE — the call
    shape varies by provider, which is why this dispatch exists instead of a
    single hardcoded client call. Callers guard provider ∈ _WIRED_PROVIDERS
    before calling, so the final branch is defensive/unreachable.
    """
    if provider == "FRED":
        return fred_client.fetch_latest_sofr(
            api_key, series_id=series_id, value_scale=value_scale, client=http_client
        )
    if provider == "BoJ":
        return boj_client.fetch_latest_tona(
            series_id=series_id, value_scale=value_scale, client=http_client
        )
    raise fred_client.FredError(
        f"internal: _fetch_live_observation called with unwired provider {provider!r} "
        "(should have been rejected by the _WIRED_PROVIDERS guard)."
    )


def _bind_one_component(
    component: dict,
    *,
    api_key: str,
    cache: SnapshotCache,
    today: date | None,
    http_client: Any | None,
) -> list[str]:
    """Bind a single api-sourced component in place. Returns error strings (empty = ok)."""
    name = component.get("name", "<unnamed>")
    formula_id = component.get("formula_id")
    source = component.get("source") or {}

    bindable = _BINDABLE.get(formula_id)
    if bindable is None:
        return [
            f"component '{name}': source.type='api' but formula_id={formula_id!r} has no "
            f"api binding (bindable: {sorted(_BINDABLE)}). Refusing to guess "
            "which input to fetch."
        ]
    field, provider, series_id, value_scale = bindable

    if provider not in _WIRED_PROVIDERS:
        return [
            f"component '{name}': source.type='api' provider={provider!r} is not wired "
            f"(wired: {sorted(_WIRED_PROVIDERS)}; Census/BLS clients are deferred). "
            "Refusing to fabricate a value from an unimplemented provider."
        ]

    mode, max_age_days, policy_errors = _parse_cache_policy(source, name)
    if policy_errors:
        return policy_errors

    inputs = component.setdefault("inputs", {})
    fetched_at = datetime.now(timezone.utc).isoformat()

    # ── Try live first (always; even cached_within_days prefers fresh) ──
    # Dispatch on provider: FRED takes an api_key; BoJ stat-search takes none.
    # Both return an object exposing .value/.observation_date/.series_id/
    # .source_url, so everything below stays provider-uniform.
    live_error: str | None = None
    try:
        obs = _fetch_live_observation(
            provider,
            api_key=api_key,
            series_id=series_id,
            value_scale=value_scale,
            http_client=http_client,
        )
    except (fred_client.FredError, boj_client.BojError) as exc:
        live_error = str(exc)
        obs = None

    if obs is not None:
        inputs[field] = obs.value
        try:
            cache.write(
                series_id=series_id,
                value=obs.value,
                observation_date=obs.observation_date,
                source_url=obs.source_url,
            )
        except OSError:
            # Cache write is best-effort; a failure to persist the snapshot must
            # NOT fail an otherwise-successful live bind. The live value is used;
            # future authorised fallbacks just won't have this snapshot.
            pass
        source["binding_result"] = {
            "field": field,
            "bound_value": obs.value,
            "source_type": SOURCE_TYPE_API,
            "series_id": series_id,
            "source_ref": obs.source_url,
            "observation_date": obs.observation_date,
            "freshness": "live",
            "fetched_at": fetched_at,
        }
        component["source"] = source
        return []

    # ── Live failed. Honest failure unless the profile authorises stale cache ──
    if mode != "cached_within_days":
        return [
            f"component '{name}': live {provider} fetch for series {series_id!r} failed and "
            f"cache_policy.mode='{mode}' does not authorise stale data. Honest failure "
            f"(GIVE-UP) rather than a wrong-but-confident rate. Underlying error: {live_error}"
        ]

    # cached_within_days: attempt the authorised fallback.
    try:
        cached = cache.read(series_id=series_id, max_age_days=max_age_days, today=today)
    except CacheMiss as exc:
        return [
            f"component '{name}': live {provider} fetch failed AND no cached snapshot within "
            f"max_age_days={max_age_days} is available. Honest failure (GIVE-UP). "
            f"Live error: {live_error}. Cache: {exc}"
        ]

    inputs[field] = cached.value
    source["binding_result"] = {
        "field": field,
        "bound_value": cached.value,
        "source_type": SOURCE_TYPE_API,
        "series_id": series_id,
        "source_ref": f"snapshot_cache:{series_id} (live {provider} unavailable)",
        "observation_date": cached.observation_date,
        "freshness": f"stale, as of {cached.observation_date}",
        "fetched_at": fetched_at,
        "stale_age_days": cached.age_days,
        "live_error": live_error,
    }
    component["source"] = source
    return []


def bind_api_sources(
    profile: dict,
    *,
    api_key: str,
    cache: SnapshotCache | None = None,
    today: date | None = None,
    http_client: Any | None = None,
) -> tuple[dict | None, list[str]]:
    """Bind every source.type=='api' component in `profile` to live (or
    profile-authorised cached) data.

    Pure w.r.t. the input: operates on a deep copy, never mutates the caller's dict.

    Args:
      profile: the merged risk-factor profile (post deep-merge).
      api_key: FRED key (from settings.fred_api_key). Blank → honest failure for
               any api-sourced component (handled inside fred_client).
      cache: SnapshotCache (defaults to the package default root).
      today: injectable current date for deterministic staleness tests.
      http_client: optional httpx.Client injected by tests.

    Returns:
      (bound_profile, errors).
        errors == [] → bound_profile is the new dict with api inputs filled.
        errors != [] → bound_profile is None (caller → validation_errors → GIVE-UP).
    """
    if cache is None:
        cache = SnapshotCache()

    work = copy.deepcopy(profile)
    components = work.get("components") or []

    api_components = [
        c for c in components
        if isinstance(c, dict) and (c.get("source") or {}).get("type") == "api"
    ]
    if not api_components:
        # Nothing to bind (offline/config_file/snapshot profile). Pass through
        # unchanged — this is the Iter-1..7 path and must stay zero-cost.
        return work, []

    errors: list[str] = []
    for component in api_components:
        errors.extend(
            _bind_one_component(
                component,
                api_key=api_key,
                cache=cache,
                today=today,
                http_client=http_client,
            )
        )

    if errors:
        return None, errors
    return work, []
