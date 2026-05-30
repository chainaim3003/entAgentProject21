"""
scripts/verify_schemas.py \u2014 validate every config file against its JSON Schema.

This is the structural check (deliverable 4 of Iteration 2). Cross-file semantic
checks (formula_id existence, inputs match component inputs_schema, mode invariants)
are enforced separately by profile_spec_validator (deliverable 5).

Run from the repo root:
    python scripts/verify_schemas.py

Exits 0 if all files pass; non-zero otherwise. Prints OK / FAIL per file with the
specific JSON-pointer + error message for any failure.

Add new (schema, file) pairs to PAIRS when new config files land. The script is
idempotent and safe to re-run after every edit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print(
        "ERROR: 'jsonschema' is not installed. From the backend venv, run:\n"
        "    pip install jsonschema",
        file=sys.stderr,
    )
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent

PAIRS: list[tuple[str, str]] = [
    # Profile schema \u2192 every profile file
    ("schemas/risk-factor-profile.schema.json",
     "config/risk-factor-profiles/export-import/_base.json"),
    ("schemas/risk-factor-profile.schema.json",
     "config/risk-factor-profiles/export-import/india-us.json"),
    ("schemas/risk-factor-profile.schema.json",
     "config/risk-factor-profiles/export-import/india-us-textiles.json"),
    ("schemas/risk-factor-profile.schema.json",
     "config/risk-factor-profiles/export-import/vietnam-us.json"),
    ("schemas/risk-factor-profile.schema.json",
     "config/risk-factor-profiles/export-import/vietnam-us-textiles.json"),

    # Profile schema -> domestic profiles (Iter-6; least-specific first)
    ("schemas/risk-factor-profile.schema.json",
     "config/risk-factor-profiles/domestic/_base_domestic.json"),
    ("schemas/risk-factor-profile.schema.json",
     "config/risk-factor-profiles/domestic/us-services.json"),
    ("schemas/risk-factor-profile.schema.json",
     "config/risk-factor-profiles/domestic/us-ecommerce.json"),

    # Profile schema -> live-data domestic variants (Iter-8 services-live;
    # Iter-9 ecommerce-live). Same profile schema; only component sources differ
    # (source.type='api'). us-services-live was authored in Iter-8 but never
    # added to PAIRS until now.
    ("schemas/risk-factor-profile.schema.json",
     "config/risk-factor-profiles/domestic/us-services-live.json"),
    ("schemas/risk-factor-profile.schema.json",
     "config/risk-factor-profiles/domestic/us-ecommerce-live.json"),

    # Component schema \u2192 every component file
    ("schemas/risk-factor-component.schema.json",
     "config/risk-factor-components/base_sofr_fed_path_linear.json"),
    ("schemas/risk-factor-component.schema.json",
     "config/risk-factor-components/tariff_gtap_quadratic.json"),
    ("schemas/risk-factor-component.schema.json",
     "config/risk-factor-components/sovereign_trapezoidal.json"),
    ("schemas/risk-factor-component.schema.json",
     "config/risk-factor-components/wc_trapezoidal.json"),

    # Hedge-spec schema \u2192 the default hedge spec
    ("schemas/hedge-spec.schema.json",
     "config/hedge-specs/_default.json"),
    ("schemas/hedge-spec.schema.json",
     "config/hedge-specs/supplied-rates-example.json"),

    # gtap-armington schema (Iter-4: gained its first file)
    ("schemas/gtap-armington.schema.json",
     "config/gtap-references/armington-elasticities.json"),

    # gtap-armington and sovereign-rating schemas have no files yet \u2014 they are
    # authoritative for when corridor-references/ and gtap-references/ are populated.
]


def main() -> int:
    ok = 0
    fail = 0
    for schema_rel, file_rel in PAIRS:
        schema_path = REPO_ROOT / schema_rel
        file_path = REPO_ROOT / file_rel
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"FAIL [{schema_rel}] could not read schema: {e}")
            fail += 1
            continue
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"FAIL {file_rel} could not read file: {e}")
            fail += 1
            continue

        errors = sorted(
            Draft202012Validator(schema).iter_errors(data),
            key=lambda e: list(e.path),
        )
        if errors:
            print(f"FAIL {file_rel}   (against {schema_rel})")
            for e in errors:
                pointer = "/".join(str(p) for p in e.path) or "<root>"
                print(f"        at {pointer}: {e.message}")
            fail += 1
        else:
            print(f"OK   {file_rel}")
            ok += 1

    total = ok + fail
    print(f"\nresult: {ok}/{total} passed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
