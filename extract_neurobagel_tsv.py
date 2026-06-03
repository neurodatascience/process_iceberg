#!/usr/bin/env python3
"""extract_neurobagel_tsv.py

Reads iceberg_neurobagel_mapping.yaml, extracts every mapped column from the
ICEBERG Excel file across multiple sheets, joins them on the composite key
(num_sujet, redcap_event_name), and writes a single TSV ready for annotation
with the Neurobagel annotation tool.

Column values are written as-is (no transformations), with one addition:
a `computed_age` column (float) is derived from birth month/year and visit
date and inserted at position 2.

Usage
-----
    python extract_neurobagel_tsv.py [--mapping FILE] [--excel FILE] [--output FILE]

See README.md or `python extract_neurobagel_tsv.py --help` for full details.
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

try:
    import pandas as pd
    import yaml
except ImportError as exc:
    sys.exit(
        f"Missing dependency: {exc}\n"
        "Install with: pip install -r requirements.txt"
    )

# ── Constants ─────────────────────────────────────────────────────────────────
JOIN_KEYS = ["num_sujet", "redcap_event_name"]
PRIMARY_SHEET = "Général"


# ── Argument parsing ──────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(
        description=(
            "Extract Neurobagel-mapped columns from the ICEBERG Excel file "
            "and write a single TSV for phenotypic annotation."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--mapping",
        default="iceberg_neurobagel_mapping.yaml",
        metavar="FILE",
        help="Neurobagel variable mapping YAML",
    )
    p.add_argument(
        "--excel",
        default="2023_04_05_Gel_Iceberg_patient1.xlsx",
        metavar="FILE",
        help="ICEBERG REDCap export Excel file",
    )
    p.add_argument(
        "--output",
        default="iceberg_neurobagel_phenotype.tsv",
        metavar="FILE",
        help="Output TSV path",
    )
    return p.parse_args()


# ── YAML traversal ────────────────────────────────────────────────────────────
def collect_columns(mapping: dict) -> dict:
    """
    Walk the mapping YAML tree and collect {sheet_name: [ordered column names]}.

    Rules:
    - The `sheet` key of any YAML dict sets the sheet context for that subtree.
    - Any dict with a `column_name` key contributes that column to the current sheet.
    - Join keys are prepended to every sheet's column list so the merge works.
    """
    ordered: dict = defaultdict(list)
    seen_per_sheet: dict = defaultdict(set)

    def _add(sheet: str, col: str):
        if not sheet or not col:
            return
        if col not in seen_per_sheet[sheet]:
            ordered[sheet].append(col)
            seen_per_sheet[sheet].add(col)

    def _walk(obj, sheet=None):
        if isinstance(obj, dict):
            # Update sheet context if this dict declares one
            raw_sheet = obj.get("sheet", sheet)
            # Skip placeholder values used in the YAML's join_keys comment
            if isinstance(raw_sheet, str) and raw_sheet.startswith("all"):
                raw_sheet = sheet
            s = raw_sheet
            if "column_name" in obj and isinstance(obj["column_name"], str):
                _add(s, obj["column_name"])
            for v in obj.values():
                _walk(v, s)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item, sheet)
        # scalars (str, int, float, None) — nothing to do

    _walk(mapping)

    # Ensure join keys are at the front of every sheet's column list
    result = {}
    for sheet, cols in ordered.items():
        front = []
        rest = []
        for c in cols:
            (front if c in JOIN_KEYS else rest).append(c)
        # Any join key not already in list gets prepended
        missing_jk = [jk for jk in JOIN_KEYS if jk not in front]
        result[sheet] = missing_jk + front + rest

    return result


# ── Sheet loading ─────────────────────────────────────────────────────────────
def load_sheet(xl: pd.ExcelFile, sheet: str, columns: list) -> pd.DataFrame:
    """
    Read a sheet from the ExcelFile, select only the requested columns,
    and warn about any that are absent.
    """
    df = pd.read_excel(xl, sheet_name=sheet)
    available = [c for c in columns if c in df.columns]
    missing = set(columns) - set(available)
    if missing:
        print(
            f"  WARNING [{sheet}]: {len(missing)} column(s) not found: "
            f"{sorted(missing)}",
            file=sys.stderr,
        )
    return df[available].copy()


def compute_age(df: pd.DataFrame) -> pd.Series:
    """
    Return age at each visit as a float (e.g. 30.5 = 30 years 6 months).

    Birth month (ddn_m) and birth year (ddn_a) are typically only recorded
    at the baseline visit, so they are propagated forward and backward within
    each subject's rows before the calculation.  Rows missing a visit date or
    birth information get NaN.
    """
    birth_m = df.groupby("num_sujet")["ddn_m"].transform(
        lambda s: s.ffill().bfill()
    )
    birth_y = df.groupby("num_sujet")["ddn_a"].transform(
        lambda s: s.ffill().bfill()
    )
    visit_date = pd.to_datetime(df["date_visite"], errors="coerce")
    age = (
        (visit_date.dt.year + visit_date.dt.month / 12.0)
        - (birth_y + birth_m / 12.0)
    )
    return age.round(2)


def filter_real_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove filler rows that have no subject number.
    REDCap exports pre-allocate rows for all subjects; un-enrolled rows
    have null or zero in num_sujet.
    """
    mask = df["num_sujet"].notna() & (df["num_sujet"].astype(str).str.strip() != "0")
    return df[mask].copy()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args = parse_args()

    mapping_path = Path(args.mapping)
    excel_path = Path(args.excel)
    output_path = Path(args.output)

    for path in (mapping_path, excel_path):
        if not path.exists():
            sys.exit(f"File not found: {path}")

    # ── Load mapping ──────────────────────────────────────────────────────────
    print(f"Mapping : {mapping_path}")
    with mapping_path.open() as f:
        mapping = yaml.safe_load(f)

    columns_by_sheet = collect_columns(mapping)
    print(
        f"Sheets  : {len(columns_by_sheet)} "
        f"({', '.join(columns_by_sheet)})"
    )
    total_cols = sum(len(v) for v in columns_by_sheet.values())
    unique_non_jk = sum(
        len([c for c in v if c not in JOIN_KEYS]) for v in columns_by_sheet.values()
    )
    print(f"Columns : {unique_non_jk} data columns across all sheets\n")

    # ── Open Excel file ───────────────────────────────────────────────────────
    print(f"Excel   : {excel_path}")
    xl = pd.ExcelFile(excel_path)

    if PRIMARY_SHEET not in columns_by_sheet:
        sys.exit(
            f"Primary sheet '{PRIMARY_SHEET}' is not referenced in the mapping."
        )

    # ── Load and filter primary sheet ─────────────────────────────────────────
    print(f"\n[1/{len(columns_by_sheet)}] Loading primary sheet: {PRIMARY_SHEET}")
    result = filter_real_rows(
        load_sheet(xl, PRIMARY_SHEET, columns_by_sheet[PRIMARY_SHEET])
    )
    print(
        f"  {len(result)} subject-visit rows  |  "
        f"{len(result.columns)} columns"
    )

    # ── Left-join each secondary sheet ────────────────────────────────────────
    secondary_sheets = [s for s in columns_by_sheet if s != PRIMARY_SHEET]
    for idx, sheet in enumerate(secondary_sheets, start=2):
        print(f"\n[{idx}/{len(columns_by_sheet)}] Merging: {sheet}")
        df = filter_real_rows(
            load_sheet(xl, sheet, columns_by_sheet[sheet])
        )

        # Only add columns not already present in result
        new_cols = [
            c for c in df.columns
            if c not in JOIN_KEYS and c not in result.columns
        ]
        if not new_cols:
            print(f"  SKIP — no new columns (all already present in result)")
            continue

        result = result.merge(
            df[JOIN_KEYS + new_cols],
            on=JOIN_KEYS,
            how="left",
        )
        print(
            f"  +{len(new_cols)} columns  →  "
            f"result now {len(result.columns)} columns"
        )

    # ── Compute age at visit ──────────────────────────────────────────────────
    print("\nComputing age at visit...")
    result.insert(2, "computed_age", compute_age(result))
    n_age = result["computed_age"].notna().sum()
    print(f"  computed_age: {n_age}/{len(result)} rows have a value")

    # ── Write output ──────────────────────────────────────────────────────────
    result.to_csv(output_path, sep="\t", index=False, na_rep="")
    print(f"\nOutput  : {output_path}")
    print(f"  Rows    : {len(result)}")
    print(f"  Columns : {len(result.columns)}")


if __name__ == "__main__":
    main()
