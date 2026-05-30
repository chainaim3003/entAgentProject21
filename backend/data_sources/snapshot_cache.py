"""
data_sources/snapshot_cache.py — dated snapshot cache for live-API values.

Iteration 8 deliverable. A small, file-backed, dated cache. Each successful
live fetch writes a snapshot stamped with the observation date; on a later
outage the profile MAY (if its cache_policy authorises) read the most recent
snapshot back, subject to a staleness check.

WHY A FILE CACHE, NOT cachetools:
  The design calls for a *dated snapshot* whose age is judged against the data's
  observation date, not a process-lifetime TTL. An in-memory TTL library
  (cachetools) would lose state across runs and couldn't express "stale, as of
  2026-05-20". A tiny JSON-on-disk cache is the honest fit and adds no
  dependency (stdlib only).

CACHE KEY:
  Keyed by (series_id) under a cache root. One file per series:
      <cache_root>/<series_id>.json
  Content mirrors the live observation plus a cached_at wall-clock stamp:
      {
        "series_id": "SOFR",
        "value": 0.0431,                # decimal fraction
        "observation_date": "2026-05-20",
        "source_url": "...REDACTED...",
        "cached_at": "2026-05-29T14:03:00+00:00"
      }

STALENESS:
  age_days is measured from observation_date (the date the rate is *for*) to
  `today`, NOT from cached_at. A rate observed 2 days ago that we cached 1 hour
  ago is 2 days stale, because that's the age of the *data*. This is the honest
  measure for "use last cached within N days".

NO LLM IMPORTS — deterministic by design (agent-type law).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

# Default cache root: backend/data_sources/_cache/. Created lazily on first write.
_THIS_DIR = Path(__file__).resolve().parent
DEFAULT_CACHE_ROOT = _THIS_DIR / "_cache"


class CacheMiss(RuntimeError):
    """Raised when no usable cached snapshot exists for a key.

    'Usable' means: a file exists, parses, and (when a max_age_days bound is
    supplied) is within that bound. A miss is honest information for the caller,
    not an error to swallow — the caller turns it into a GIVE-UP when the live
    fetch also failed.
    """


@dataclass(frozen=True)
class CachedSnapshot:
    """A cached observation read back from disk."""

    series_id: str
    value: float
    observation_date: str
    source_url: str
    cached_at: str
    age_days: int


class SnapshotCache:
    """File-backed dated snapshot cache. One JSON file per series_id."""

    def __init__(self, cache_root: Path | str | None = None) -> None:
        self.cache_root = Path(cache_root) if cache_root is not None else DEFAULT_CACHE_ROOT

    def _path_for(self, series_id: str) -> Path:
        # series_id is a short FRED identifier (e.g. "SOFR"); guard against path
        # traversal just in case a profile ever carries an unexpected value.
        safe = "".join(c for c in series_id if c.isalnum() or c in ("-", "_"))
        if not safe:
            raise ValueError(f"snapshot_cache: unusable series_id {series_id!r}")
        return self.cache_root / f"{safe}.json"

    def write(
        self,
        *,
        series_id: str,
        value: float,
        observation_date: str,
        source_url: str,
    ) -> Path:
        """Persist a successful live observation as a dated snapshot.

        Returns the path written. Creates the cache root if needed.
        """
        self.cache_root.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "series_id": series_id,
            "value": value,
            "observation_date": observation_date,
            "source_url": source_url,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        path = self._path_for(series_id)
        # Atomic-ish write: temp then replace, so a crash mid-write can't leave a
        # half-written snapshot that a later run would treat as authoritative.
        tmp = path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
        tmp.replace(path)
        return path

    def read(
        self,
        *,
        series_id: str,
        max_age_days: int | None = None,
        today: date | None = None,
    ) -> CachedSnapshot:
        """Read the cached snapshot for a series.

        Args:
          series_id: e.g. "SOFR".
          max_age_days: if given, a snapshot older than this (by observation_date)
                        raises CacheMiss. If None, age is reported but not gated.
          today: injectable "current date" for deterministic tests; defaults to
                 today's UTC date.

        Returns:
          CachedSnapshot with computed age_days.

        Raises:
          CacheMiss if no file, unparseable, or beyond max_age_days.
        """
        path = self._path_for(series_id)
        if not path.is_file():
            raise CacheMiss(
                f"snapshot_cache: no cached snapshot for series {series_id!r} at {path}."
            )
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise CacheMiss(
                f"snapshot_cache: cached snapshot for {series_id!r} at {path} is "
                f"unreadable: {exc}."
            ) from exc

        obs_date_raw = data.get("observation_date")
        try:
            obs_date = date.fromisoformat(str(obs_date_raw)[:10])
        except ValueError as exc:
            raise CacheMiss(
                f"snapshot_cache: cached snapshot for {series_id!r} has an unparseable "
                f"observation_date {obs_date_raw!r}: {exc}."
            ) from exc

        ref_today = today or datetime.now(timezone.utc).date()
        age_days = (ref_today - obs_date).days

        if max_age_days is not None and age_days > max_age_days:
            raise CacheMiss(
                f"snapshot_cache: cached snapshot for {series_id!r} is {age_days} day(s) "
                f"old (observation_date={obs_date.isoformat()}), exceeding the profile's "
                f"max_age_days={max_age_days}. Refusing to use stale data the profile "
                "did not authorise."
            )

        value = data.get("value")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise CacheMiss(
                f"snapshot_cache: cached snapshot for {series_id!r} has a non-numeric "
                f"value {value!r}."
            )

        return CachedSnapshot(
            series_id=series_id,
            value=float(value),
            observation_date=obs_date.isoformat(),
            source_url=str(data.get("source_url", "")),
            cached_at=str(data.get("cached_at", "")),
            age_days=age_days,
        )
