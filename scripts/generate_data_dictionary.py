#!/usr/bin/env python3
"""generate_data_dictionary.py

Produces a long-form data dictionary (TSV) for the ICEBERG Neurobagel pipeline.

Output columns
--------------
  column_name   Variable name as it appears in the TSV
  description   Human-readable description of what the variable measures
  assessment    Assessment tool the variable belongs to (blank for demographics)
  variable_type Categorical / Binary / Ordinal / Integer score / Continuous / Identifier
  coded_value   The value as it appears in the TSV (float-formatted for numeric codes)
  value_label   Human-readable meaning of that value; "[missing]" for missing codes

One row is emitted per (column, value) pair, so the file doubles as a lookup
table: join on (column_name, coded_value) to annotate a synthetic or real TSV.

Usage
-----
    python generate_data_dictionary.py [--mapping FILE] [--tsv-template FILE]
                                       [--output FILE]
"""

import argparse
import math
import sys
from pathlib import Path

try:
    import pandas as pd
    import yaml
except ImportError as exc:
    sys.exit(f"Missing dependency: {exc}\nInstall with: pip install -r requirements.txt")


# ── Helpers ───────────────────────────────────────────────────────────────────

def to_float_str(val: str) -> str:
    if val == "":
        return ""
    try:
        return str(float(val))
    except (ValueError, TypeError):
        return str(val)


def normalize_missing(vals) -> list:
    result = []
    for v in (vals or []):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            result.append("")
        elif isinstance(v, str) and v.strip().lower() in ("nan", ".nan"):
            result.append("")
        else:
            result.append(str(v))
    # Deduplicate, preserving order
    seen, out = set(), []
    for v in result:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


# Map the 8 known REDCap event names to readable labels
_SESSION_LABELS: dict = {
    "v0_arm_1":                    "Visit 0 — baseline",
    "v1_arm_1":                    "Visit 1 — ~1 year",
    "v2_arm_1":                    "Visit 2 — ~2 years",
    "v3_arm_1":                    "Visit 3 — ~3 years",
    "v4_arm_1":                    "Visit 4 — ~4 years",
    "m6_optionnel__6_mo_arm_1":    "Visit M6 — optional 6-month",
    "gen_arm_1":                   "General / administrative event",
    "covid19_arm_1":               "COVID-19 follow-up event",
}


# ── YAML parsing ──────────────────────────────────────────────────────────────

def parse_column_specs(mapping: dict) -> dict:
    """
    Walk the YAML and return {column_name: spec_dict}.

    Spec keys: description, assessment_name, variable_type, levels, range,
               missing_values, unique_values.
    Parent-level missing_values and assessment_name are inherited by children.
    """
    specs: dict = {}

    def walk(obj, sheet=None, assessment=None, inherited_missing=None):
        if isinstance(obj, dict):
            s = obj.get("sheet", sheet)
            a = obj.get("assessment_name", assessment)
            local_missing = normalize_missing(
                obj.get("missing_values", inherited_missing or [])
            )
            if "column_name" in obj and isinstance(obj["column_name"], str):
                col = obj["column_name"]
                entry = {
                    "description":    obj.get("description") or "",
                    "assessment_name": a or "",
                    "variable_type":  obj.get("variable_type") or "",
                    "levels":         obj.get("levels") or {},
                    "range":          obj.get("range"),
                    "missing_values": normalize_missing(
                        obj.get("missing_values", local_missing)
                    ),
                    "unique_values":  list(obj.get("unique_values") or []),
                }
                if col not in specs:
                    specs[col] = entry
                else:
                    # Merge: fill in any fields the first encounter left empty
                    existing = specs[col]
                    for field in ("description", "assessment_name", "variable_type"):
                        if not existing[field] and entry[field]:
                            existing[field] = entry[field]
                    for field in ("levels", "unique_values"):
                        if not existing[field] and entry[field]:
                            existing[field] = entry[field]
                    if existing["range"] is None and entry["range"] is not None:
                        existing["range"] = entry["range"]
                    if not existing["missing_values"] and entry["missing_values"]:
                        existing["missing_values"] = entry["missing_values"]
            for v in obj.values():
                walk(v, s, a, local_missing)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, sheet, assessment, inherited_missing)

    walk(mapping)
    return specs


# ── Variable-type inference ───────────────────────────────────────────────────

def infer_type(col: str, spec: dict) -> str:
    """Infer a readable variable-type label from the spec and column name."""
    explicit = spec.get("variable_type")
    if explicit:
        return explicit

    if spec.get("levels"):
        return "Categorical"
    if spec.get("unique_values"):
        return "Categorical"

    r = spec.get("range")
    if r is not None:
        lo, hi = r
        if hi == 1:
            return "Binary (0/1)"
        if hi is not None and hi <= 10:
            return "Ordinal"
        return "Integer score"

    n = col.lower()
    if "num_sujet" in n or "redcap_event" in n:
        return "Identifier"
    if "age" in n or "date" in n or "ddn" in n:
        return "Continuous"
    if "examen_realise" in n or n in {"upsit_done", "psg_nd", "moc_nd"}:
        return "Binary (0/1)"
    if "complete" in n:
        return "Categorical"  # REDCap completion codes
    return "Continuous"


# ── Description fallback ──────────────────────────────────────────────────────

def infer_description(col: str, spec: dict) -> str:
    if spec.get("description"):
        return spec["description"]

    n = col.lower()
    if n == "computed_age":
        return "Age at visit in decimal years (e.g. 57.0 = 57 years), derived from birth date and visit date"
    if "num_sujet" in n:
        return "Unique participant number"
    if "redcap_event" in n:
        return "REDCap event identifier encoding the study visit"
    if "examen_realise" in n:
        return f"Was the assessment performed at this visit? (1=Yes, 0=No)"
    if "non_raison" in n or "_rais" in n or "incomp_rais" in n:
        return "Reason the assessment was not performed (free text)"
    if "comment" in n:
        return "Examiner comment (free text)"
    if "complete" in n:
        return "REDCap form completion status (0=incomplete, 1=unverified, 2=complete)"
    if "date" in n:
        return "Date (ISO format YYYY-MM-DD, or Excel serial number)"
    if "time" in n:
        return "Time of examination"
    if "calc" in n:
        return f"Calculated score: {col}"
    return col.replace("_", " ").capitalize()


# ── Row generation ────────────────────────────────────────────────────────────

def rows_for_column(col: str, spec: dict) -> list:
    """
    Return a list of (column_name, description, assessment, variable_type,
    coded_value, value_label) tuples for this column.
    """
    description  = infer_description(col, spec)
    assessment   = spec.get("assessment_name") or ""
    vtype        = infer_type(col, spec)
    missing      = spec.get("missing_values", [])
    rows         = []
    coded_seen   = set()

    def add(coded_val, label):
        if coded_val not in coded_seen:
            coded_seen.add(coded_val)
            rows.append((col, description, assessment, vtype, coded_val, label))

    def add_missing_rows():
        for mv in missing:
            coded = to_float_str(mv) if mv != "" else ""
            add(coded, "[missing]")

    # ── Categorical (has explicit level dict) ─────────────────────────────────
    if spec.get("levels"):
        for key, label in spec["levels"].items():
            add(to_float_str(key), label)
        add_missing_rows()

    # ── Session identifier (known unique values with readable labels) ─────────
    elif spec.get("unique_values"):
        for val in spec["unique_values"]:
            label = _SESSION_LABELS.get(str(val), str(val))
            add(str(val), label)
        add_missing_rows()

    # ── Identifier (no levels, no range, flagged or inferred as identifier) ───
    elif vtype == "Identifier":
        add("(any)", "Unique participant or session identifier")

    # ── Binary [0, 1] ────────────────────────────────────────────────────────
    elif vtype == "Binary (0/1)":
        add("0.0", "No / Not present / Not performed")
        add("1.0", "Yes / Present / Performed")
        add_missing_rows()

    # ── Ordinal or integer score (has range) ─────────────────────────────────
    elif spec.get("range") is not None:
        lo, hi = spec["range"]
        lo = int(lo) if lo is not None else 0
        if hi is None:
            add("(non-negative integer)", f"Score starting at {lo}; no documented upper bound")
        elif (hi - lo) <= 30:
            # Enumerate every integer value
            for i in range(lo, int(hi) + 1):
                add(str(float(i)), f"Score value {i} (range {lo}–{int(hi)})")
        else:
            add(f"{lo}–{int(hi)}", f"Integer score in range [{lo}, {int(hi)}]")
        add_missing_rows()

    # ── Continuous or unknown ─────────────────────────────────────────────────
    else:
        add("(continuous)", description)
        add_missing_rows()

    # Special-case: REDCap completion codes (override generic rows)
    if "complete" in col.lower() and vtype == "Categorical":
        rows.clear()
        coded_seen.clear()
        add("0.0", "Incomplete")
        add("1.0", "Unverified")
        add("2.0", "Complete")
        add_missing_rows()

    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Generate a long-form data dictionary / lookup table for the ICEBERG pipeline TSVs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--mapping",
                   default="static/iceberg_neurobagel_mapping.yaml", metavar="FILE")
    p.add_argument("--tsv-template",
                   default="output/iceberg_neurobagel_phenotype.tsv", metavar="FILE",
                   help="Real or synthetic TSV (only column names/order are used)")
    p.add_argument("--output",
                   default="output/iceberg_data_dictionary.tsv", metavar="FILE")
    return p.parse_args()


def main():
    args = parse_args()

    for f in (Path(args.mapping), Path(args.tsv_template)):
        if not f.exists():
            sys.exit(f"File not found: {f}")

    print(f"Mapping      : {args.mapping}")
    with open(args.mapping) as fh:
        mapping = yaml.safe_load(fh)
    specs = parse_column_specs(mapping)

    # computed_age is derived at runtime; inject its spec
    specs.setdefault("computed_age", {
        "description":    "Age at visit in decimal years (e.g. 57.0), derived from birth date and visit date",
        "assessment_name": "",
        "variable_type":  "Continuous",
        "levels": {}, "range": None,
        "missing_values": [""], "unique_values": [],
    })
    print(f"  {len(specs)} column specs")

    print(f"Template     : {args.tsv_template}")
    columns = pd.read_csv(args.tsv_template, sep="\t", nrows=0).columns.tolist()
    print(f"  {len(columns)} columns")

    print("\nBuilding dictionary rows...")
    all_rows = []
    for col in columns:
        all_rows.extend(rows_for_column(col, specs.get(col, {})))

    df = pd.DataFrame(all_rows, columns=[
        "column_name", "description", "assessment_tool",
        "variable_type", "coded_value", "value_label",
    ])

    output_path = Path(args.output)
    df.to_csv(output_path, sep="\t", index=False)

    print(f"\nOutput       : {output_path}")
    print(f"  Dictionary rows : {len(df)}")
    print(f"  Columns covered : {df['column_name'].nunique()} / {len(columns)}")

    print("\nSample entries:")
    sample_cols = ["sexe", "groupe", "computed_age", "trail_moca", "mds_3_1_off",
                   "redcap_event_name", "examen_realise_moca", "diag_olf"]
    for col in sample_cols:
        chunk = df[df["column_name"] == col]
        if not chunk.empty:
            print(f"\n  {col}:")
            print(chunk[["coded_value", "value_label"]].to_string(index=False))


if __name__ == "__main__":
    main()
