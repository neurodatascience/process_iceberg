#!/usr/bin/env python3
"""generate_synthetic_tsv.py

Generates a synthetic phenotypic TSV with the same column names and order as
the real iceberg_neurobagel_phenotype.tsv, but filled with made-up values.

Coverage guarantee: for every column documented in the YAML mapping, every
possible categorical level and every expected missing-value code appears at
least once.  For integer-scored columns with a small range (≤30 values), every
integer in the range also appears at least once.  For wider ranges and purely
continuous columns (age, dates) a representative sample of plausible values is
generated instead of exhaustive enumeration.

The output is intended for validating the Neurobagel annotation tool without
using real participant data.

Usage
-----
    python generate_synthetic_tsv.py [--mapping FILE] [--tsv-template FILE]
                                     [--output FILE] [--n-rows N]
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


# ── Formatting helpers ────────────────────────────────────────────────────────

def to_float_str(val: str) -> str:
    """
    Return the float-notation string for a numeric value ('1' → '1.0').
    Non-numeric values are returned unchanged; empty string stays empty.
    This matches how pandas writes integer-like columns that contain NaN
    (upcasted to float64, so 1 becomes 1.0 in the TSV).
    """
    if val == "":
        return ""
    try:
        return str(float(val))
    except (ValueError, TypeError):
        return str(val)


def normalize_missing(vals) -> list:
    """
    Convert NaN-like and None entries in a missing-values list to ''.

    PyYAML's SafeLoader parses `NaN` (no leading dot) as the string "NaN"
    rather than float('nan'), so we handle both the float and string forms.
    """
    result = []
    for v in (vals or []):
        if v is None:
            result.append("")
        elif isinstance(v, float) and math.isnan(v):
            result.append("")
        elif isinstance(v, str) and v.strip().lower() in ("nan", ".nan"):
            result.append("")
        else:
            result.append(str(v))
    return result


# ── YAML walking ──────────────────────────────────────────────────────────────

def parse_column_specs(mapping: dict) -> dict:
    """
    Walk the mapping YAML and return {column_name: spec_dict}.

    Spec keys: variable_type, levels, range, missing_values, unique_values.

    missing_values declared at a parent level (e.g. per-assessment block) are
    inherited by child column entries that don't declare their own — this is how
    the per-assessment `missing_values: ["", NaN]` propagates to every item.
    """
    specs: dict = {}

    def walk(obj, sheet=None, inherited_missing=None):
        if isinstance(obj, dict):
            s = obj.get("sheet", sheet)
            # Resolve the missing-values list applicable to this level's children
            local_missing = normalize_missing(
                obj.get("missing_values", inherited_missing or [])
            )
            if "column_name" in obj and isinstance(obj["column_name"], str):
                col = obj["column_name"]
                if col not in specs:  # first encounter wins
                    specs[col] = {
                        "variable_type": obj.get("variable_type"),
                        "levels":        obj.get("levels") or {},
                        "range":         obj.get("range"),
                        # Use column-level missing if present, else inherit from parent
                        "missing_values": normalize_missing(
                            obj.get("missing_values", local_missing)
                        ),
                        "unique_values":  list(obj.get("unique_values") or []),
                    }
            for v in obj.values():
                walk(v, s, local_missing)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, sheet, inherited_missing)

    walk(mapping)
    return specs


# ── Required-value generation ─────────────────────────────────────────────────

# Fallback pools for columns that are absent from or sparsely described in the YAML.
_FALLBACK: dict = {
    "computed_age": ["55.08", "62.33", "48.75", "70.5",  "51.0", "67.25"],
    "date_visite":  ["2014-11-06", "2016-03-15", "2018-09-01", "2020-12-20"],
    "ddn_m":        ["1.0",  "6.0",  "11.0"],
    "ddn_a":        ["1945.0", "1960.0", "1975.0"],
}


def _name_fallback(col: str) -> list:
    """Infer plausible required values from the column name alone."""
    n = col.lower()
    if "examen_realise" in n or n in {"upsit_done", "psg_nd", "moc_nd"}:
        return ["1.0", "0.0"]
    if "complete" in n:
        return ["2.0", "1.0", "0.0"]       # REDCap completion codes
    if "non_raison" in n or "_rais" in n or "incomp_rais" in n:
        return ["Raison inconnue"]          # free-text field
    if "comment" in n:
        return ["RAS"]
    if "num_sujet" in n:
        return ["1", "2", "3", "4", "5"]
    if "redcap_event" in n:
        return ["v0_arm_1", "v1_arm_1", "v2_arm_1", "v3_arm_1", "v4_arm_1"]
    if "date" in n or "time" in n:
        return ["2014-11-06", "2016-03-15", "2018-09-01"]
    if "ddn" in n:
        return ["11.0", "1945.0"]
    # Safe default: treat as binary flag
    return ["1.0", "0.0"]


def required_values(col: str, spec: dict) -> list:
    """
    Return the ordered list of string values that must appear at least once in
    column `col`.

    Strategy (first matching rule wins):
      1. unique_values list in spec  → use those directly
      2. levels dict                 → use level keys formatted as floats
      3. range [lo, hi]              → enumerate all integers if span ≤ 30;
                                       otherwise sample ~15 evenly-spread values
      4. column name in _FALLBACK    → use the fallback pool
      5. name heuristic              → _name_fallback()

    Missing-value codes from spec['missing_values'] are appended at the end.
    All numeric values use float notation ('1.0') to match pandas float64 output.
    """
    vals: list = []

    if spec.get("unique_values"):
        vals = [str(v) for v in spec["unique_values"]]

    elif spec.get("levels"):
        vals = [to_float_str(k) for k in spec["levels"].keys()]

    elif spec.get("range") is not None:
        lo, hi = spec["range"]
        lo = int(lo) if lo is not None else 0
        if hi is None:
            # Unknown upper bound — generate 5 plausible values from lo onward
            vals = [str(float(lo + i)) for i in (0, 2, 5, 9, 14)]
        else:
            hi = int(hi)
            span = hi - lo
            if span <= 30:
                vals = [str(float(i)) for i in range(lo, hi + 1)]
            else:
                step = max(1, span // 15)
                vals = [str(float(i)) for i in range(lo, hi, step)] + [str(float(hi))]

    elif col in _FALLBACK:
        vals = list(_FALLBACK[col])

    else:
        vals = _name_fallback(col)

    # --- Append missing-value codes, formatted consistently ---
    for mv in spec.get("missing_values", []):
        formatted = to_float_str(mv) if mv != "" else ""
        if formatted not in vals:
            vals.append(formatted)

    # Deduplicate preserving order
    seen: set = set()
    out: list = []
    for v in vals:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


# ── DataFrame assembly ────────────────────────────────────────────────────────

def build_synthetic_df(columns: list, specs: dict, n_rows: int) -> pd.DataFrame:
    """
    Build the synthetic DataFrame.  Each column cycles through its required
    values so that every value appears at least once, then repeats from the
    start to fill `n_rows` rows.
    """
    data = {}
    for col in columns:
        req = required_values(col, specs.get(col, {})) or [""]
        data[col] = [req[i % len(req)] for i in range(n_rows)]
    return pd.DataFrame(data, columns=columns)


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description=(
            "Generate a synthetic phenotypic TSV covering every documented "
            "value in the YAML mapping."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--mapping",
                   default="iceberg_neurobagel_mapping.yaml", metavar="FILE",
                   help="Neurobagel variable mapping YAML")
    p.add_argument("--tsv-template",
                   default="iceberg_neurobagel_phenotype.tsv", metavar="FILE",
                   help="Real phenotype TSV (only column names/order are used)")
    p.add_argument("--output",
                   default="iceberg_neurobagel_synthetic.tsv", metavar="FILE",
                   help="Output synthetic TSV path")
    p.add_argument("--n-rows", type=int, default=35, metavar="N",
                   help="Minimum rows (extended automatically if any column needs more)")
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
    # computed_age is derived at extraction time; add its spec manually
    specs.setdefault("computed_age", {
        "variable_type": "Continuous",
        "levels": {}, "range": None,
        "missing_values": [""], "unique_values": [],
    })
    print(f"  {len(specs)} column specs parsed from YAML")

    print(f"Template     : {args.tsv_template}")
    columns = pd.read_csv(args.tsv_template, sep="\t", nrows=0).columns.tolist()
    print(f"  {len(columns)} columns")

    # Determine row count: must cover the column that needs the most distinct values
    n_rows = args.n_rows
    for col in columns:
        n = len(required_values(col, specs.get(col, {})))
        if n > n_rows:
            n_rows = n

    print(f"\nGenerating {n_rows} synthetic rows...")
    df = build_synthetic_df(columns, specs, n_rows)

    output_path = Path(args.output)
    df.to_csv(output_path, sep="\t", index=False)

    print(f"\nOutput       : {output_path}")
    print(f"  Rows       : {len(df)}")
    print(f"  Columns    : {len(df.columns)}")

    print("\nSpot-check unique values (selected columns):")
    spot = {
        "sexe":        "categorical (2 valid + 2 missing codes)",
        "groupe":      "categorical (5 valid + 2 missing codes)",
        "computed_age":"continuous sample + missing",
        "total_moca":  "integer range [0,30] + missing",
        "mds_3_1_off": "integer range [0,4] + missing",
        "nmss_1":      "binary [0,1] + missing",
    }
    for col, note in spot.items():
        if col in df.columns:
            uvals = sorted(set(df[col].tolist()), key=lambda x: (x == "", x))
            print(f"  {col:30s} ({note})")
            print(f"    → {uvals}")


if __name__ == "__main__":
    main()
