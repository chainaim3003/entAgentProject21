"""
data_sources — live free-API clients + dated snapshot cache for V2 risk-factor
binding (Iteration 8+).

Iteration 8 binds ONLY FRED (SOFR) for the base_sofr component's `initial`
input. Census/BLS clients land in Iteration 9.

DESIGN DISCIPLINE (design-v1-free-apis.md §8 + the §0 thread of the iteration
plan: "no silent fallbacks, no hardcoding, no mocks; honest failure is preferred
to a wrong answer"):

  - A live fetch that fails (network down, non-200, malformed payload, missing
    observation) RAISES. There is no silent substitution of a stale value.
  - Stale cached data may be used ONLY when the consuming profile explicitly
    authorises it via source.cache_policy.mode == "cached_within_days" and the
    cached snapshot is within max_age_days. In that case the binding is stamped
    `freshness="stale, as of <date>"` so the provenance trail is honest.
  - Offline/CI runs never reach this package: profiles using
    source.type == "config_file" (the snapshot-backed Iter-6/7 profiles) skip
    api binding entirely.

Public surface:
  fred_client.FredError, fred_client.fetch_latest_sofr
  boj_client.BojError, boj_client.fetch_latest_tona
  snapshot_cache.SnapshotCache, snapshot_cache.CacheMiss
  api_binding.ApiBindingError, api_binding.bind_api_sources
"""

from __future__ import annotations

from . import api_binding, boj_client, fred_client, snapshot_cache

__all__ = ["api_binding", "boj_client", "fred_client", "snapshot_cache"]
