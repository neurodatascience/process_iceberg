#!/usr/bin/env python3
"""build_imaging_table.py

Reads the phenotype TSV produced by extract_neurobagel_tsv.py, consults the
imaging_modality_flags section of the YAML mapping to discover which flag
columns correspond to which Neurobagel/BIDS modality, and writes a Neurobagel
imaging table with one row per (subject, session, acquired modality).

Output columns (Neurobagel imaging table format):
  sub     — participant identifier, copied verbatim from num_sujet in the TSV
  ses     — session identifier, copied verbatim from redcap_event_name in the TSV
  suffix  — BIDS modality suffix (T1w, T2w, dwi, bold, …)
  path    — left empty; fill in actual file paths before submitting to Neurobagel

Only modalities with a known Neurobagel term (neurobagel_modality != null in
the YAML) produce rows. Flags without a mapping (irm_fait, irm_r2, irm_melan,
datsc_real) are silently skipped.

Usage
-----
    python build_imaging_table.py [--mapping FILE] [--tsv FILE] [--output FILE]

See README.md or `python build_imaging_table.py --help` for details.
"""

import argparse
import sys
from pathlib import Path

try:
    import pandas as pd
    import yaml
except ImportError as exc:
    sys.exit(
        f"Missing dependency: {exc}\n"
        "Install with: pip install -r requirements.txt"
    )

# Maps every Neurobagel/NIDM imaging term to its BIDS file suffix.
# Mirrors https://github.com/neurobagel/communities/blob/main/configs/Neurobagel/imaging_modalities.json
NIDM_TO_SUFFIX = {
    "nidm:T1Weighted":               "T1w",
    "nidm:T2Weighted":               "T2w",
    "nidm:DiffusionWeighted":        "dwi",
    "nidm:FlowWeighted":             "bold",
    "nidm:ArterialSpinLabeling":     "asl",
    "nidm:Electroencephalography":   "eeg",
    "nidm:Magnetoencephalography":   "meg",
    "nidm:PositronEmissionTomography": "pet",
}


def parse_args():
    p = argparse.ArgumentParser(
        description=(
            "Build a Neurobagel imaging table from ICEBERG imaging availability flags."
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
        "--tsv",
        default="iceberg_neurobagel_phenotype.tsv",
        metavar="FILE",
        help="Phenotype TSV produced by extract_neurobagel_tsv.py",
    )
    p.add_argument(
        "--output",
        default="iceberg_neurobagel_imaging.tsv",
        metavar="FILE",
        help="Output imaging table TSV path",
    )
    return p.parse_args()


def load_modality_map(mapping: dict) -> dict:
    """
    Return {flag_column_name: bids_suffix} for every imaging flag in the YAML
    that has a non-null neurobagel_modality with a known BIDS suffix.

    Flags without a Neurobagel modality (irm_fait, irm_r2, irm_melan,
    datsc_real) are excluded.
    """
    section = mapping.get("imaging_modality_flags", {})
    modality_map = {}
    skipped = []

    for col_entry in section.get("columns", []):
        col_name = col_entry.get("column_name")
        nidm_term = col_entry.get("neurobagel_modality")

        if not nidm_term:
            skipped.append(col_name)
            continue

        suffix = NIDM_TO_SUFFIX.get(nidm_term)
        if not suffix:
            print(
                f"  WARNING: unknown NIDM term '{nidm_term}' for '{col_name}' "
                "— skipping",
                file=sys.stderr,
            )
            skipped.append(col_name)
            continue

        modality_map[col_name] = suffix

    if skipped:
        print(f"  Skipped (no Neurobagel modality mapping): {skipped}")

    return modality_map


def build_table(tsv_path: Path, modality_map: dict) -> pd.DataFrame:
    """
    Read the phenotype TSV and return a DataFrame with columns
    [sub, ses, suffix, path] — one row per (subject, session, acquired modality).

    A modality is considered acquired when its flag column equals 1 (or 1.0).
    Rows where the flag is 0, NaN, or absent produce no imaging table entry.
    """
    pheno = pd.read_csv(tsv_path, sep="\t", dtype=str)

    missing_flags = [c for c in modality_map if c not in pheno.columns]
    if missing_flags:
        sys.exit(
            f"Imaging flag column(s) not found in TSV: {missing_flags}\n"
            "Run extract_neurobagel_tsv.py first to regenerate the phenotype TSV."
        )

    rows = []
    for _, row in pheno.iterrows():
        sub = row["num_sujet"]
        ses = row["redcap_event_name"]

        # Skip rows that have no subject or session identifier
        if pd.isna(sub) or pd.isna(ses) or str(sub).strip() == "":
            continue

        for flag_col, suffix in modality_map.items():
            val = row.get(flag_col, "")
            # Flag is acquired only when the cell contains exactly "1" or "1.0"
            try:
                acquired = float(val) == 1.0
            except (ValueError, TypeError):
                acquired = False

            if acquired:
                rows.append({"sub": sub, "ses": ses, "suffix": suffix, "path": ""})

    return pd.DataFrame(rows, columns=["sub", "ses", "suffix", "path"])


def main():
    args = parse_args()

    mapping_path = Path(args.mapping)
    tsv_path = Path(args.tsv)
    output_path = Path(args.output)

    for path in (mapping_path, tsv_path):
        if not path.exists():
            sys.exit(f"File not found: {path}")

    print(f"Mapping : {mapping_path}")
    with mapping_path.open() as f:
        mapping = yaml.safe_load(f)

    print("Building modality map from YAML...")
    modality_map = load_modality_map(mapping)
    print(
        f"  {len(modality_map)} mappable flag(s): "
        + ", ".join(f"{col}→{sfx}" for col, sfx in modality_map.items())
    )

    print(f"\nTSV     : {tsv_path}")
    table = build_table(tsv_path, modality_map)

    table.to_csv(output_path, sep="\t", index=False)
    print(f"\nOutput  : {output_path}")
    print(f"  Rows    : {len(table)}")
    if not table.empty:
        counts = table.groupby("suffix").size().to_dict()
        print(f"  By suffix: {counts}")
    print(
        "\n  NOTE: 'path' column is empty — populate with actual file paths "
        "before submitting to Neurobagel."
    )


if __name__ == "__main__":
    main()
