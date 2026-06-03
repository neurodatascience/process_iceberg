# ICEBERG → Neurobagel Data Pipeline

This directory contains scripts and configuration files for extracting and
annotating phenotypic and imaging data from the ICEBERG cohort (a longitudinal
Parkinson's disease study) so it can be ingested into a
[Neurobagel](https://neurobagel.org) graph.

---

## Quick start

```bash
# 1. Install dependencies into your environment of choice
pip install -r requirements.txt   # or: uv pip install -r requirements.txt

# 2. Run the extraction
make
```

---

## Directory layout

```
.
├── 2023_04_05_Gel_Iceberg_patient1.xlsx   # Source data (REDCap export)
├── iceberg_neurobagel_mapping.yaml        # Variable mapping (do not hand-edit indices)
├── extract_neurobagel_tsv.py              # Script 1 — extract to TSV
├── requirements.txt                       # Python dependencies
├── Makefile                               # Automation
└── README.md                             # This file
```

Generated outputs:

```
iceberg_neurobagel_phenotype.tsv           # Wide TSV ready for Neurobagel annotation  (make extract)
iceberg_neurobagel_imaging.tsv             # Neurobagel imaging table                  (make imaging)
iceberg_neurobagel_synthetic.tsv           # Synthetic test TSV for annotation testing (make synthetic)
```

---

## Requirements

- **Python 3.11+** with `pandas`, `openpyxl`, and `PyYAML` installed.
  See `requirements.txt`.
- The ICEBERG Excel file must be present in this directory.

---

## Scripts

### `extract_neurobagel_tsv.py` — Step 1: Column extraction

Reads `iceberg_neurobagel_mapping.yaml`, loads the relevant columns from each
sheet of the Excel file, joins them on the composite key
`(num_sujet, redcap_event_name)`, and writes a single wide TSV.

```bash
# Default invocation (controlled by Makefile variables)
make extract

# With custom paths
python extract_neurobagel_tsv.py \
    --mapping  iceberg_neurobagel_mapping.yaml \
    --excel    2023_04_05_Gel_Iceberg_patient1.xlsx \
    --output   iceberg_neurobagel_phenotype.tsv

# Get help
python extract_neurobagel_tsv.py --help
```

**What it does:**
1. Parses the mapping YAML to discover which columns are needed from each sheet.
2. Loads the `Général` sheet as the primary frame (it contains all subject-visit rows).
3. Left-joins each other sheet (`Neuropsy`, `Motrice`, `Non motrice`, `Imagerie`)
   on `(num_sujet, redcap_event_name)`.
4. Filters out empty filler rows (rows where `num_sujet` is null, common in
   REDCap exports where rows are pre-allocated for all participants).
5. Writes the result as a tab-separated file with empty cells for missing values.

**Column values are written as-is.** Notable points for downstream use:

| Column(s) | Note |
|-----------|------|
| `date_visite` | Written as an ISO date string (e.g. `2014-11-06`) — openpyxl auto-converts Excel date cells when the cell has a date format applied. If the full-cohort export stores dates as bare integers instead, use: `pd.to_datetime(col - 25569, unit='D', origin='unix')` |
| `ddn_m`, `ddn_a` | Birth month and year. Age at visit must be computed from these + `date_visite`. |
| `sexe` | Coded: `1` = Male, `2` = Female. See mapping YAML for Neurobagel SNOMED terms. |
| `groupe` / `statut_inclusion` | Coded 1–5. See mapping YAML for group definitions and Neurobagel term URLs. |
| `nmss_1`–`nmss_30` | Binary (0/1) in this dataset — **not** the standard freq × severity NMSS scoring. |
| `irm_*`, `datsc_real` | Binary imaging availability flags (1 = acquired). Not annotatable via the Neurobagel phenotypic annotation tool; used to build the imaging table in a later step. |

---

### `build_imaging_table.py` — Step 2: Imaging table

Reads `iceberg_neurobagel_mapping.yaml` for the flag→modality mappings and
the phenotype TSV for the actual flag values, then writes a Neurobagel imaging
table with one row per (subject × session × acquired modality).

```bash
make imaging

# Or directly:
python build_imaging_table.py \
    --mapping iceberg_neurobagel_mapping.yaml \
    --tsv     iceberg_neurobagel_phenotype.tsv \
    --output  iceberg_neurobagel_imaging.tsv
```

**Output columns:** `sub`, `ses`, `suffix`, `path`

- `sub` / `ses` — copied verbatim from `num_sujet` / `redcap_event_name` in the
  phenotype TSV so the two tables can be linked by Neurobagel.
- `suffix` — BIDS modality suffix derived from the `neurobagel_modality` field
  in the YAML (`T1w`, `T2w`, `dwi`, `bold`).
- `path` — **left empty**. You must populate this column with the actual paths
  to the imaging files on disk before submitting the table to Neurobagel.

Flags without a Neurobagel modality mapping (`irm_fait`, `irm_r2`, `irm_melan`,
`datsc_real`) are silently skipped.

### `generate_synthetic_tsv.py` — Step 3: Synthetic annotation test data

Generates a synthetic TSV with the same column names and order as the real
phenotype TSV, but with made-up values.  Every documented categorical level
and every expected missing-value code appears at least once in its column.
For integer-scored columns with a range of ≤ 30 values, all integers in the
range are included.  For wider ranges and continuous columns a representative
sample of plausible values is generated.

```bash
# Requires the real phenotype TSV to already exist (for column order)
make extract
make synthetic

# Or directly:
python generate_synthetic_tsv.py \
    --mapping      iceberg_neurobagel_mapping.yaml \
    --tsv-template iceberg_neurobagel_phenotype.tsv \
    --output       iceberg_neurobagel_synthetic.tsv
```

The synthetic TSV contains no real participant data and is safe to share for
annotation tests.

### Future scripts (planned)

*(none currently)*

---

## Neurobagel annotation workflow

After running `make extract`, the TSV goes through the Neurobagel annotation tool:

1. **Generate TSV** — `make extract` → `iceberg_neurobagel_phenotype.tsv`
2. **Annotate phenotypic variables** — open the TSV in the
   [Neurobagel annotation tool](https://annotate.neurobagel.org). Use
   `iceberg_neurobagel_mapping.yaml` as the reference for:
   - Which columns map to which `nb:` term
   - Level-to-SNOMED-term mappings for `sexe` and `groupe`
   - Which assessment tools to associate with each column group
3. **Resolve TBD term URLs** — the mapping YAML flags several assessment tools
   (Mattis DRS, FAB, SCOPA-AUT, NMSS, Epworth, UPSIT, iRBD, at-risk relative)
   as `TBD`. Look up their SNOMED or NLX/NeuroBridge term identifiers before
   annotation.
4. **Build imaging table** — run `build_imaging_table.py` (step 2, once written)
   to generate the companion imaging TSV.

---

## Variable mapping reference

`iceberg_neurobagel_mapping.yaml` is the authoritative record of which Excel
columns map to which Neurobagel concept. It is also the input to the extraction
script — **do not rename or move it**.

The file is organised into two top-level sections:

| Section | Purpose |
|---------|---------|
| `neurobagel_variables` | Columns annotatable in the Neurobagel phenotypic annotation tool |
| `imaging_modality_flags` | Binary flags for imaging modalities; used to build the imaging table |

Column indices in the YAML are **0-based** and **sheet-specific**.
The `Général` sheet has an unnamed blank column at index 3 (`Unnamed: 3`)
from the REDCap export; this shifts all subsequent column indices by +1
relative to the Dictionnaire sheet's logical ordering.

---

## Makefile targets

| Target | Action |
|--------|--------|
| `make` / `make all` | Run extraction + build imaging table |
| `make extract` | Run phenotype extraction script |
| `make imaging` | Build Neurobagel imaging table |
| `make synthetic` | Generate synthetic annotation test TSV |
| `make clean` | Remove all generated TSV files |
| `make help` | Print available targets |

Override any variable on the command line:

```bash
make extract EXCEL=path/to/full_dataset.xlsx TSV_OUT=full_cohort.tsv
```
