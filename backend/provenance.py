"""
provenance.py - N6a Provenance Agent (Iteration-5 full I7 invariant).

PLACEMENT
=========
Per design-v1-detailed-design.md section 1 (textual graph), edges e14 + e15:
    e14   N6   DISCLOSURE   -> N6a  PROVENANCE
    e15   N6a  PROVENANCE   -> N8   MEMORY
N6a runs AFTER N6 (disclosure), BEFORE N8 (memory).

ITERATION-5 SCOPE (this iteration)
==================================
Replaces the Iteration-3 minimal "never raises" contract with the full I7
invariant per design-v1-detailed-design.md section 1 (structural lines):

  PROVENANCE INVARIANT (I7)
    Every numeric input to N4 traces in audit_log to one of:
      (a) a config file path + sha256 checksum,
      (b) a free-API URL + timestamp + response sha256,
      (c) a caller-supplied input + the message/field where it arrived.
    N6a verifies this at run-time; if a knot input has no source, it raises
    and the run fails.

For Iteration 5, only (a) and (c) are used. Source-type (b) "api" is reserved
for Iteration 8+ when FRED/Census/BLS bindings activate; for Iter-5 it is a
defined constant but no stamps are emitted under it.

WHAT GETS STAMPED
=================
  derived mode (dispatch=draps_v1):
    - simulation_result.sofr_path[i].value  -> config_file (profile leaf)
    - simulation_result.swap_now_fixed_rate -> config_file (hedge spec)
    - simulation_result.swap_later_fixed_rate -> config_file (hedge spec)
    - validated_inputs.loan.{notional_usd,spread_bps,term_months,start_date}
                                            -> caller_supplied
    Additionally, the report includes resolved_profile_files (every layer of
    the merge, base+corridor+commodity, with sha256 each) and
    resolved_hedge_spec_file. These are file-level attributions; the
    per-numeric stamps point at the leaf-most layer (the file by which the
    profile is identified). The merge chain is in the report so the audit
    trail covers the full deep_merge_in_order chain per
    design-v1-config-architecture.md section 4.

  supplied mode:
    - knot_payload.supplied.sofr_path[i].value -> caller_supplied
    - knot_payload.supplied.swap_now_fixed     -> caller_supplied
    - knot_payload.supplied.swap_later_fixed   -> caller_supplied
    - validated_inputs.loan.*                  -> caller_supplied
    No file-level attributions (no profile/spec files drove the numerics).

DESIGN NOTE: PER-POINT SOFR ATTRIBUTION FOR DISPATCH=DRAPS_V1
=============================================================
Per design-v1-iteration-plan.md section 1 ITERATION 5 acceptance: the report
"enumerates every numeric in sofr_path". For dispatch=draps_v1 (Iter-5's only
shipped derived path) DRAPS computes the SOFR points inside its inline
Postman JS using the merged profile's component inputs. V2 does not see the
per-component contribution to each point. The honest attribution is therefore
per SOFR point, source_ref = profile leaf file. Iter-4 left dispatch=v2_direct
deferred; when v2_direct ships, per-(point,component) attribution becomes
possible and this module's derived branch will be extended.

I7 ENFORCEMENT
==============
Every required input that is absent or non-numeric raises
ProvenanceInvariantError. There is no error-recovery edge from N6a in graph.py
(only N3c has one), so a raise here halts the LangGraph run honestly. The
disclosure node has already produced disclosure_doc by the time N6a runs, but
memory_node has not -> a failed run leaves no memory record. This matches the
acceptance text: "A run with missing source attribution raises and fails
honestly (no silent pass)."

LOAN-FIELD SOURCE TYPE
======================
Loan fields arrive via the caller's POST /run body (private_loan_doc + prompt
extracted by N1/N2/N3). Per design-v1-detailed-design section 1 I7 (c), this
qualifies as "caller-supplied input + the message/field where it arrived".
source_ref records the request -> validated_inputs chain for traceability.

NO LLM IMPORTS - deterministic by design (agent-type law).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Source-type taxonomy
#
# Three-element set per design-v1-iteration-plan.md section 1 ITERATION 5
# acceptance + design-v1-detailed-design.md section 1 invariant I7.
# ---------------------------------------------------------------------------

SOURCE_TYPE_CONFIG_FILE     = "config_file"
SOURCE_TYPE_API             = "api"  # reserved for Iter-8+ (FRED/Census/BLS)
SOURCE_TYPE_CALLER_SUPPLIED = "caller_supplied"

LEGAL_SOURCE_TYPES = frozenset({
    SOURCE_TYPE_CONFIG_FILE,
    SOURCE_TYPE_API,
    SOURCE_TYPE_CALLER_SUPPLIED,
})


# ---------------------------------------------------------------------------
# Filesystem anchors (config files live under the repo root, two parents up
# from this module per the established backend/ layout).
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT   = _BACKEND_DIR.parent


# Loan numeric fields stamped on every run (both modes). order matters: the
# stamps appear in the report in this order. start_date is stamped even though
# it isn't a number, because the I7 invariant says "every numeric input to N4
# AND loan fields" -> the iteration-plan acceptance enumerates "loan fields"
# explicitly, of which start_date is one.
_LOAN_FIELDS: tuple[str, ...] = (
    "notional_usd",
    "spread_bps",
    "term_months",
    "start_date",
)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class ProvenanceInvariantError(RuntimeError):
    """Raised by N6a when I7 cannot be satisfied. Halts the run honestly.

    Per design-v1-iteration-plan.md section 1 ITERATION 5: "A run with a
    missing source attribution raises and fails honestly (no silent pass)."
    There is no recovery edge from N6a in the graph; a raise here propagates
    through LangGraph and the whole run fails.
    """


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _audit_entry(node: str, summary: str, output: dict[str, Any]) -> dict[str, Any]:
    return {
        "node": node,
        "summary": summary,
        "output": output,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _is_number(v: Any) -> bool:
    """Strict numeric check: rejects bool (which is a subclass of int in Python)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _sha256_of_file(rel_path: str) -> str:
    """Compute sha256 of a project-relative file path.

    Raises ProvenanceInvariantError (not OSError) if the file is missing,
    because for I7 enforcement purposes a missing source file IS a missing
    attribution. The message names the resolved absolute path so the operator
    can investigate.
    """
    abs_path = _REPO_ROOT / rel_path
    if not abs_path.is_file():
        raise ProvenanceInvariantError(
            f"provenance: cannot compute sha256 for {rel_path!r} "
            f"(resolved to {abs_path}; file not found). "
            "I7 requires every config_file source to resolve to a real file."
        )
    h = hashlib.sha256()
    with abs_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_stamp(
    *,
    field: str,
    value: Any,
    source_type: str,
    source_ref: str,
    checksum_or_ts: str,
) -> dict[str, Any]:
    """Construct one stamp in the I7-mandated shape.

    Stamp keys are exactly {field, value, source_type, source_ref,
    checksum_or_ts} per design-v1-detailed-design.md section 2
    (HedgeAdvisorStateV2 knot_payload.provenance).

    Defensive on source_type: raises ValueError (NOT
    ProvenanceInvariantError) if the source_type is outside the legal set.
    This is an internal-bug guard, not an I7 violation -- a bug in this module
    that constructs the wrong source_type should not be reported as a missing
    attribution; the operator needs to know it's an internal defect.
    """
    if source_type not in LEGAL_SOURCE_TYPES:
        raise ValueError(
            f"internal bug in provenance_node: illegal source_type "
            f"{source_type!r}. Must be one of: {sorted(LEGAL_SOURCE_TYPES)}."
        )
    return {
        "field":           field,
        "value":           value,
        "source_type":     source_type,
        "source_ref":      source_ref,
        "checksum_or_ts":  checksum_or_ts,
    }


def _resolve_hedge_spec_path(state: dict) -> str | None:
    """Recover the hedge-spec source path for sha256 hashing.

    The N3b hedge_spec_resolver writes the relative source path into
    audit_log[?node=='hedge_spec_resolver'].output.source. We read it from
    there because that's the authoritative record of which file the
    resolver actually loaded.

    Note: an earlier sketch of this helper also tried to derive a path from
    state.hedge_spec_id (e.g. 'default-3-scenario' -> 'config/hedge-specs/
    default-3-scenario.json'). That fallback was removed because
    state.hedge_spec_id is the spec_id FIELD INSIDE the JSON, not the
    filename. The Iter-1 stub hardcodes loading _default.json regardless of
    requested id (per PROJECT_CONTEXT.md section 6 item 2), so the mapping is
    not 1:1. Real runs always traverse N3b and the audit_log entry exists;
    tests that construct state directly must include the audit entry too.

    Returns None if no audit_log entry is found; the caller raises with a
    concrete I7 message.
    """
    for entry in (state.get("audit_log") or []):
        if entry.get("node") == "hedge_spec_resolver":
            src = (entry.get("output") or {}).get("source")
            if isinstance(src, str) and src.strip():
                return src
    return None


# ---------------------------------------------------------------------------
# Stamp builders
# ---------------------------------------------------------------------------

def _stamp_loan_fields(state: dict, request_timestamp: str) -> list[dict[str, Any]]:
    """Loan fields -> caller_supplied stamps (both modes).

    Per design-v1-detailed-design section 1 I7 (c): caller-supplied input
    + the message/field where it arrived. The source_ref records the
    "request body -> validated_inputs.loan.X" chain so downstream auditors
    can trace each loan numeric to its arrival point at the agent boundary.

    Raises ProvenanceInvariantError if validated_inputs.loan is missing,
    not a dict, or missing any required field.
    """
    validated = state.get("validated_inputs") or {}
    loan = validated.get("loan")
    if not isinstance(loan, dict):
        raise ProvenanceInvariantError(
            f"provenance: I7 violation - validated_inputs.loan is "
            f"{type(loan).__name__}, expected dict. Cannot attribute loan "
            "fields. Upstream N3 validator must populate it."
        )

    stamps: list[dict[str, Any]] = []
    missing: list[str] = []
    for fld in _LOAN_FIELDS:
        val = loan.get(fld)
        # Treat None or blank string as missing. Empty-string start_date is
        # caught here too. Numeric zeros are allowed (a 0% spread is valid).
        if val is None or (isinstance(val, str) and not val.strip()):
            missing.append(fld)
            continue
        stamps.append(_build_stamp(
            field=f"validated_inputs.loan.{fld}",
            value=val,
            source_type=SOURCE_TYPE_CALLER_SUPPLIED,
            source_ref=f"request.body.private_loan_doc -> validated_inputs.loan.{fld}",
            checksum_or_ts=request_timestamp,
        ))

    if missing:
        raise ProvenanceInvariantError(
            f"provenance: I7 violation - loan fields missing from "
            f"validated_inputs.loan: {missing}. Required: {list(_LOAN_FIELDS)}."
        )
    return stamps


def _stamp_supplied_block(supplied: dict, request_timestamp: str) -> list[dict[str, Any]]:
    """Caller-supplied SOFR path + 2 fixed rates -> caller_supplied stamps.

    Used by supplied-mode runs only. The supplied block is the verbatim copy
    of state['supplied'] that the composer placed onto knot_payload['supplied'].
    The composer's _validate_supplied_block is the strict upstream gate; this
    function repeats the numeric checks because N6a must independently verify
    I7 (the composer could conceivably be bypassed in future iterations).

    Raises ProvenanceInvariantError on any missing or non-numeric value.
    """
    stamps: list[dict[str, Any]] = []

    sofr_path = supplied.get("sofr_path")
    if not isinstance(sofr_path, list) or not sofr_path:
        raise ProvenanceInvariantError(
            "provenance: I7 violation - knot_payload.supplied.sofr_path is "
            "missing or not a non-empty list. Cannot attribute supplied SOFR path."
        )

    for i, pt in enumerate(sofr_path):
        if not isinstance(pt, dict) or not _is_number(pt.get("value")):
            raise ProvenanceInvariantError(
                f"provenance: I7 violation - knot_payload.supplied.sofr_path[{i}] "
                f"has no numeric 'value' field; cannot attribute."
            )
        stamps.append(_build_stamp(
            field=f"knot_payload.supplied.sofr_path[{i}].value",
            value=pt["value"],
            source_type=SOURCE_TYPE_CALLER_SUPPLIED,
            source_ref=f"request.body.supplied.sofr_path[{i}].value",
            checksum_or_ts=request_timestamp,
        ))

    for key in ("swap_now_fixed", "swap_later_fixed"):
        val = supplied.get(key)
        if not _is_number(val):
            raise ProvenanceInvariantError(
                f"provenance: I7 violation - knot_payload.supplied.{key} is not "
                f"numeric (got {type(val).__name__}); cannot attribute."
            )
        stamps.append(_build_stamp(
            field=f"knot_payload.supplied.{key}",
            value=val,
            source_type=SOURCE_TYPE_CALLER_SUPPLIED,
            source_ref=f"request.body.supplied.{key}",
            checksum_or_ts=request_timestamp,
        ))

    return stamps


def _stamp_derived_sofr_and_rates(state: dict) -> tuple[
    list[dict[str, Any]],
    str,   # profile leaf path (relative)
    str,   # profile leaf sha256
    str,   # hedge-spec path (relative)
    str,   # hedge-spec sha256
]:
    """Derived-mode SOFR points + 2 fixed rates -> config_file stamps.

    For dispatch=draps_v1, DRAPS computes the SOFR path inside its inline
    Postman JS using the merged profile's component inputs and outputs the
    resulting path under environmentVariables.SOFR_PATH. draps_client
    (Iter-5 extension) surfaces it onto simulation_result.sofr_path. Each
    point is stamped to the profile leaf (the most-specific layer in the
    merge chain). The full merge chain with sha256s is collected separately
    by provenance_node into resolved_profile_files.

    The two fixed rates are stamped to the hedge-spec file (where the
    discount_from_path rule and discount basis-points are defined).

    Raises ProvenanceInvariantError on any missing or non-numeric value,
    or if the profile / hedge-spec files cannot be resolved or hashed.
    """
    sim = state.get("simulation_result") or {}

    sofr_path = sim.get("sofr_path")
    if not isinstance(sofr_path, list) or not sofr_path:
        raise ProvenanceInvariantError(
            "provenance: I7 violation - simulation_result.sofr_path is missing "
            "or not a non-empty list. DRAPS may have returned an unrecognized "
            "shape; see draps_client._extract_scenarios. Cannot attribute "
            "derived SOFR path."
        )

    swap_now   = sim.get("swap_now_fixed_rate")
    swap_later = sim.get("swap_later_fixed_rate")
    if not _is_number(swap_now):
        raise ProvenanceInvariantError(
            f"provenance: I7 violation - simulation_result.swap_now_fixed_rate "
            f"is {type(swap_now).__name__}, expected number; cannot attribute."
        )
    if not _is_number(swap_later):
        raise ProvenanceInvariantError(
            f"provenance: I7 violation - simulation_result.swap_later_fixed_rate "
            f"is {type(swap_later).__name__}, expected number; cannot attribute."
        )

    # Profile leaf and its sha256. Resolver writes profile_resolution_path
    # in most-specific-first order, so [0] is the leaf.
    profile_paths = state.get("profile_resolution_path") or []
    if not profile_paths:
        raise ProvenanceInvariantError(
            "provenance: I7 violation - profile_resolution_path is empty. "
            "Cannot attribute derived SOFR path to a config_file source."
        )
    leaf_path = profile_paths[0]
    if not isinstance(leaf_path, str) or not leaf_path.strip():
        raise ProvenanceInvariantError(
            f"provenance: I7 violation - profile_resolution_path[0] is "
            f"{leaf_path!r}, expected a non-empty relative path string."
        )
    leaf_sha = _sha256_of_file(leaf_path)

    # Hedge-spec path + sha256.
    spec_path = _resolve_hedge_spec_path(state)
    if not spec_path:
        raise ProvenanceInvariantError(
            "provenance: I7 violation - cannot recover hedge-spec source path "
            "from audit_log[?node=='hedge_spec_resolver'].output.source. "
            "Required to attribute swap_now_fixed_rate and "
            "swap_later_fixed_rate to a config_file source."
        )
    spec_sha = _sha256_of_file(spec_path)

    stamps: list[dict[str, Any]] = []
    for i, pt in enumerate(sofr_path):
        if not isinstance(pt, dict) or not _is_number(pt.get("value")):
            raise ProvenanceInvariantError(
                f"provenance: I7 violation - simulation_result.sofr_path[{i}] "
                f"has no numeric 'value' field; cannot attribute."
            )
        stamps.append(_build_stamp(
            field=f"simulation_result.sofr_path[{i}].value",
            value=pt["value"],
            source_type=SOURCE_TYPE_CONFIG_FILE,
            source_ref=leaf_path,
            checksum_or_ts=leaf_sha,
        ))

    stamps.append(_build_stamp(
        field="simulation_result.swap_now_fixed_rate",
        value=float(swap_now),
        source_type=SOURCE_TYPE_CONFIG_FILE,
        source_ref=spec_path,
        checksum_or_ts=spec_sha,
    ))
    stamps.append(_build_stamp(
        field="simulation_result.swap_later_fixed_rate",
        value=float(swap_later),
        source_type=SOURCE_TYPE_CONFIG_FILE,
        source_ref=spec_path,
        checksum_or_ts=spec_sha,
    ))

    return stamps, leaf_path, leaf_sha, spec_path, spec_sha


# ---------------------------------------------------------------------------
# Node entry point
# ---------------------------------------------------------------------------

def provenance_node(state: dict) -> dict:
    """N6a - deterministic. Walks run state, attributes every numeric, raises on miss.

    Iteration-5 full I7 enforcement per design-v1-iteration-plan.md section 1
    ITERATION 5 and design-v1-detailed-design.md section 1 invariant I7.

    Behaviour:
      derived mode  -> per-point SOFR stamps + 2 fixed-rate stamps
                       (config_file sources) + loan field stamps
                       (caller_supplied).
      supplied mode -> per-point SOFR stamps + 2 fixed-rate stamps
                       (caller_supplied, from knot_payload.supplied) +
                       loan field stamps (caller_supplied).
      missing input -> ProvenanceInvariantError; LangGraph propagates the
                       raise and the run fails honestly (no silent pass).

    CONTRACT
      Reads  state.knot_payload                (mode disambiguation)
             state.simulation_result           (derived: sofr_path + 2 rates)
             state.validated_inputs.loan       (loan fields)
             state.profile_resolution_path     (derived: layered file list)
             state.audit_log[?node=='hedge_spec_resolver'].output.source
                                                (recover spec file path)
      Writes state.provenance_report = {
                stamps, mode, stamped_at, summary,
                resolved_profile_files (derived only),
                resolved_hedge_spec_file (derived only),
             }
             state.audit_log                   (one entry appended)
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    knot = state.get("knot_payload")
    if not isinstance(knot, dict):
        raise ProvenanceInvariantError(
            "provenance: I7 violation - knot_payload is missing or not a dict; "
            f"got {type(knot).__name__}. Upstream composer (N3d) must produce "
            "knot_payload before N6a can attribute."
        )

    supplied = knot.get("supplied")
    is_supplied_mode = supplied is not None

    # --------------------------------------------------------------------
    # Supplied-mode branch
    # --------------------------------------------------------------------
    if is_supplied_mode:
        if not isinstance(supplied, dict):
            raise ProvenanceInvariantError(
                f"provenance: I7 violation - knot_payload['supplied'] is "
                f"{type(supplied).__name__}, expected dict. Cannot attribute."
            )
        supplied_stamps = _stamp_supplied_block(supplied, timestamp)
        loan_stamps     = _stamp_loan_fields(state, timestamp)
        stamps = supplied_stamps + loan_stamps
        report = {
            "stamps":     stamps,
            "mode":       "supplied",
            "stamped_at": timestamp,
            "summary":    (
                f"I7 satisfied: stamped {len(stamps)} numeric(s) "
                f"({len(supplied_stamps)} from knot_payload.supplied + "
                f"{len(loan_stamps)} loan field(s); all caller_supplied)"
            ),
        }
        return {
            "provenance_report": report,
            "audit_log": [
                _audit_entry(
                    "provenance",
                    f"I7 satisfied: {len(stamps)} stamp(s) emitted (supplied)",
                    {
                        "stamp_count":      len(stamps),
                        "mode":             "supplied",
                        "sofr_path_points": len(supplied.get("sofr_path") or []),
                        "fields_stamped":   [s["field"] for s in stamps],
                    },
                )
            ],
        }

    # --------------------------------------------------------------------
    # Derived-mode branch (dispatch=draps_v1 for Iter-5)
    # --------------------------------------------------------------------
    derived_stamps, leaf_path, leaf_sha, spec_path, spec_sha = \
        _stamp_derived_sofr_and_rates(state)
    loan_stamps = _stamp_loan_fields(state, timestamp)
    stamps = derived_stamps + loan_stamps

    # Full merge chain (every layered profile file + its sha256). The
    # per-numeric stamps point to the leaf; this list covers the whole
    # _base + corridor + commodity chain per design-v1-config-architecture
    # section 4 deep_merge_in_order.
    resolved_profile_files = [
        {"path": p, "sha256": _sha256_of_file(p)}
        for p in (state.get("profile_resolution_path") or [])
    ]

    report = {
        "stamps":     stamps,
        "mode":       "derived",
        "stamped_at": timestamp,
        "summary":    (
            f"I7 satisfied: stamped {len(stamps)} numeric(s) "
            f"({len(derived_stamps)} config_file from "
            f"profile leaf + hedge spec, "
            f"{len(loan_stamps)} caller_supplied loan field(s))"
        ),
        "resolved_profile_files":   resolved_profile_files,
        "resolved_hedge_spec_file": {"path": spec_path, "sha256": spec_sha},
    }
    return {
        "provenance_report": report,
        "audit_log": [
            _audit_entry(
                "provenance",
                f"I7 satisfied: {len(stamps)} stamp(s) emitted (derived)",
                {
                    "stamp_count":             len(stamps),
                    "mode":                    "derived",
                    "sofr_path_points":        len(
                        (state.get("simulation_result") or {}).get("sofr_path") or []
                    ),
                    "resolved_profile_layers": len(resolved_profile_files),
                    "profile_leaf":            leaf_path,
                    "hedge_spec":              spec_path,
                },
            )
        ],
    }
