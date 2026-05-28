"""
profile_spec_validator.py \u2014 N3c Profile-and-Spec Validator.

ITERATION-2 IMPLEMENTATION. Four check categories per
design-v1-config-architecture.md \u00a76:

  1. JSON Schema check on the resolved profile  (schemas/risk-factor-profile.schema.json)
  2. JSON Schema check on the resolved hedge spec (schemas/hedge-spec.schema.json)
  3. Cross-file: every component.formula_id referenced in the profile must exist
     as a component spec file at config/risk-factor-components/{formula_id}.json,
     AND every profile-supplied inputs.* key must satisfy that component's
     inputs_schema (type + min/max + nested object recursion).
  4. Mode invariants: mode=derived requires components[] and no supplied block;
     mode=supplied requires supplied{sofr_path, swap_now_fixed_rate, swap_later_fixed_rate}
     and no components[]; mode=derived_domestic requires components[] and no supplied.

The validator NEVER short-circuits \u2014 it accumulates ALL errors so the user sees
the full failure surface in one pass.

It also reads existing state.validation_errors and propagates them (so an
upstream resolver failure that left a None profile is reported by give_up
alongside any new errors this node finds).

ROUTING
=======
This node returns validation_errors when any check fails; the conditional edge
`route_after_profile_spec_validator` in graph.py routes:
   pass (no errors)  \u2192 composer
   fail (errors)     \u2192 give_up

CONTRACT
========
  Reads  state.resolved_risk_profile
         state.resolved_hedge_spec
         state.validation_errors    (carry-forward from upstream)
  Writes state.validation_errors    (existing + own; replaced, not appended)
         state.audit_log            (always; one entry)

NO LLM IMPORTS \u2014 deterministic by design (agent-type law).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent

_SCHEMAS_DIR = _REPO_ROOT / "schemas"
_PROFILE_SCHEMA_PATH = _SCHEMAS_DIR / "risk-factor-profile.schema.json"
_HEDGE_SPEC_SCHEMA_PATH = _SCHEMAS_DIR / "hedge-spec.schema.json"
_COMPONENTS_DIR = _REPO_ROOT / "config" / "risk-factor-components"


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Helpers
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def _audit_entry(node: str, summary: str, output: dict[str, Any]) -> dict[str, Any]:
    return {
        "node": node,
        "summary": summary,
        "output": output,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _prefix(prefix: str, errors: list[str]) -> list[str]:
    return [f"{prefix}: {e}" for e in errors]


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Check 1+2 \u2014 JSON Schema
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def _run_jsonschema(data: dict, schema_path: Path) -> list[str]:
    """Run a JSON Schema check; return a list of human-readable error strings."""
    try:
        with schema_path.open("r", encoding="utf-8") as f:
            schema = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return [f"could not load schema {schema_path.name}: {e}"]

    errors: list[str] = []
    for err in Draft202012Validator(schema).iter_errors(data):
        pointer = "/".join(str(p) for p in err.path) or "<root>"
        errors.append(f"at {pointer}: {err.message}")
    return errors


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Check 3 \u2014 cross-file: formula_id existence + inputs vs inputs_schema
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

# Component inputs_schema is a hand-written mini-schema, not JSON Schema. Shape:
#   {key: {"type": "number"|"integer"|"string"|"object", "min": ..., "max": ...,
#          "properties": {...}}}
# We check declared keys, types, numeric bounds, and recurse into nested objects.

def _is_finite_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_value_against_mini_schema(
    value: Any, field_schema: dict, path: str
) -> list[str]:
    errors: list[str] = []
    expected = field_schema.get("type")

    if expected == "number":
        if not _is_finite_number(value):
            errors.append(f"{path}: expected number, got {type(value).__name__}")
            return errors
    elif expected == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"{path}: expected integer, got {type(value).__name__}")
            return errors
    elif expected == "string":
        if not isinstance(value, str):
            errors.append(f"{path}: expected string, got {type(value).__name__}")
            return errors
    elif expected == "object":
        if not isinstance(value, dict):
            errors.append(f"{path}: expected object, got {type(value).__name__}")
            return errors
        props = field_schema.get("properties") or {}
        for k, v in value.items():
            sub_schema = props.get(k)
            if sub_schema is None:
                errors.append(f"{path}.{k}: not declared in inputs_schema")
            else:
                errors.extend(
                    _check_value_against_mini_schema(v, sub_schema, f"{path}.{k}")
                )
        return errors
    # If `expected` is something else or None, we skip the type check; bound checks
    # below still apply when value is numeric. This is intentionally permissive so
    # the validator never crashes on a component author's omission.

    if expected in ("number", "integer") and _is_finite_number(value):
        if "min" in field_schema and value < field_schema["min"]:
            errors.append(f"{path}: value {value} < min {field_schema['min']}")
        if "max" in field_schema and value > field_schema["max"]:
            errors.append(f"{path}: value {value} > max {field_schema['max']}")

    return errors


def _check_component_cross_file(profile_component: dict) -> list[str]:
    """For one profile component: verify formula_id resolves to a component file
    AND every input key satisfies that component's inputs_schema.
    """
    errors: list[str] = []
    name = profile_component.get("name", "<unnamed>")
    formula_id = profile_component.get("formula_id")

    if not formula_id:
        return [f"component '{name}': missing formula_id"]

    component_file = _COMPONENTS_DIR / f"{formula_id}.json"
    if not component_file.is_file():
        return [
            f"component '{name}': formula_id='{formula_id}' has no file at "
            f"config/risk-factor-components/{formula_id}.json"
        ]

    try:
        with component_file.open("r", encoding="utf-8") as f:
            component_spec = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return [f"component '{name}': failed to read {component_file.name}: {e}"]

    inputs_schema = component_spec.get("inputs_schema")
    if inputs_schema is None:
        # Component declares no inputs_schema (null). Per spec we cannot validate.
        return errors

    inputs = profile_component.get("inputs") or {}
    for key, value in inputs.items():
        field_schema = inputs_schema.get(key)
        if field_schema is None:
            errors.append(
                f"component '{name}' (formula={formula_id}): input '{key}' "
                f"is not declared in {formula_id}.inputs_schema"
            )
            continue
        errors.extend(
            _check_value_against_mini_schema(
                value, field_schema, f"{name}.inputs.{key}"
            )
        )

    return errors


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Check 4 \u2014 mode invariants
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

_VALID_MODES = {"derived", "supplied", "derived_domestic"}


def _check_mode_invariants(profile: dict) -> list[str]:
    """mode == 'derived'         => components[] present, no supplied block.
       mode == 'supplied'        => supplied{sofr_path, swap_now_fixed_rate,
                                            swap_later_fixed_rate} present, no components.
       mode == 'derived_domestic'=> components[] present, no supplied block.
    """
    errors: list[str] = []
    mode = profile.get("mode")
    has_components = bool(profile.get("components"))
    supplied = profile.get("supplied")
    has_supplied = supplied is not None

    if mode is None:
        return ["profile missing required 'mode' field"]
    if mode not in _VALID_MODES:
        return [f"profile has unknown mode='{mode}' (expected one of {sorted(_VALID_MODES)})"]

    if mode == "derived":
        if not has_components:
            errors.append("mode='derived' requires non-empty 'components' array")
        if has_supplied:
            errors.append("mode='derived' must NOT include a 'supplied' block "
                          "(mutually exclusive with components)")

    elif mode == "supplied":
        if not has_supplied:
            errors.append("mode='supplied' requires a 'supplied' block")
        else:
            if not supplied.get("sofr_path"):
                errors.append("mode='supplied' requires supplied.sofr_path[]")
            if "swap_now_fixed_rate" not in supplied:
                errors.append("mode='supplied' requires supplied.swap_now_fixed_rate")
            if "swap_later_fixed_rate" not in supplied:
                errors.append("mode='supplied' requires supplied.swap_later_fixed_rate")
        if has_components:
            errors.append("mode='supplied' must NOT include a 'components' array "
                          "(mutually exclusive with supplied)")

    elif mode == "derived_domestic":
        if not has_components:
            errors.append("mode='derived_domestic' requires non-empty 'components' array")
        if has_supplied:
            errors.append("mode='derived_domestic' must NOT include a 'supplied' block")

    return errors


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Node entry point
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def profile_spec_validator_node(state: dict) -> dict:
    """N3c \u2014 deterministic. Validate the merged profile + resolved hedge spec.

    Accumulates ALL errors across all four checks (no short-circuit) so the user
    sees the full failure surface in one pass. Propagates any upstream
    validation_errors so a None profile from a failed N3a still routes to give_up
    with the original cause attached.
    """
    profile = state.get("resolved_risk_profile")
    spec = state.get("resolved_hedge_spec")
    existing_errors = list(state.get("validation_errors") or [])

    own_errors: list[str] = []

    # If upstream left us with no profile or no spec, we can't run the checks.
    # Record the gap but don't dereference None.
    if profile is None and not existing_errors:
        own_errors.append(
            "resolved_risk_profile is None and no upstream errors were recorded "
            "(profile_resolver may have a bug)"
        )
    if spec is None and not existing_errors:
        own_errors.append(
            "resolved_hedge_spec is None and no upstream errors were recorded "
            "(hedge_spec_resolver may have a bug)"
        )

    if profile is not None:
        own_errors.extend(_prefix("profile schema", _run_jsonschema(profile, _PROFILE_SCHEMA_PATH)))
        own_errors.extend(_prefix("mode invariant", _check_mode_invariants(profile)))
        for comp in profile.get("components") or []:
            own_errors.extend(_prefix("cross-file", _check_component_cross_file(comp)))

    if spec is not None:
        own_errors.extend(_prefix("hedge-spec schema", _run_jsonschema(spec, _HEDGE_SPEC_SCHEMA_PATH)))

    all_errors = existing_errors + own_errors

    if all_errors:
        summary = (
            f"\u2717 validation failed: {len(all_errors)} error(s) "
            f"(carried={len(existing_errors)}, new={len(own_errors)})"
        )
        return {
            "validation_errors": all_errors,
            "audit_log": [
                _audit_entry(
                    "profile_spec_validator",
                    summary,
                    {
                        "carried_errors": existing_errors,
                        "new_errors": own_errors,
                        "profile_id": (profile or {}).get("profile_id"),
                        "spec_id": (spec or {}).get("spec_id"),
                    },
                )
            ],
        }

    return {
        "audit_log": [
            _audit_entry(
                "profile_spec_validator",
                f"\u2713 profile + spec valid (profile_id={profile.get('profile_id')}, "
                f"spec_id={spec.get('spec_id')})",
                {
                    "profile_id": profile.get("profile_id"),
                    "spec_id": spec.get("spec_id"),
                    "checks_run": ["jsonschema_profile", "jsonschema_spec",
                                   "mode_invariants", "cross_file_formula_ids",
                                   "cross_file_inputs"],
                },
            )
        ],
    }
