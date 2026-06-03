# ICEBERG → Neurobagel Data Pipeline

This directory contains scripts and configuration files for extracting and
annotating phenotypic and imaging data from the ICEBERG cohort (a longitudinal
Parkinson's disease study) so it can be ingested into a
[Neurobagel](https://neurobagel.org) graph.

---

## Quick start

```bash
make          # installs dependencies and runs the extraction
```

The first run takes ~30 seconds to install packages into `.venv/`.
Subsequent runs use the cached environment and are fast.

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

Generated outputs (created by `make extract`):

```
iceberg_neurobagel_phenotype.tsv           # Wide TSV ready for Neurobagel annotation
```

---

## Requirements

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager.
  Expected at `/home/node/.local/bin/uv` or anywhere on `PATH`.
  Install with: `curl -LsSf https://astral.sh/uv/install.sh | sh`
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

### Future scripts (planned)

**`compute_age.py`** — Step 1b *(planned)*
Adds a computed `age_at_visit` column derived from `ddn_m`, `ddn_a`, and
`date_visite`. Required before Neurobagel annotation because `nb:Age` expects
a numeric age value.

**`build_imaging_table.py`** — Step 2 *(planned)*
Reads the TSV output and the imaging flag columns (`irm_3dt1`, `irm_3dt2`,
`irm_tdif`, `irm_rs`, `irm_r2`, `irm_melan`, `datsc_real`) to produce a
Neurobagel imaging table (columns: `sub`, `ses`, `suffix`, `path`).
See [Neurobagel imaging data docs](https://neurobagel.org/user_guide/preparing_imaging_data/).

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
| `make` / `make all` | Install dependencies, then run extraction |
| `make install` | Create `.venv` and install packages |
| `make extract` | Run extraction script |
| `make clean` | Remove `.venv` and generated TSV |
| `make help` | Print available targets |

Override any variable on the command line:

```bash
make extract EXCEL=path/to/full_dataset.xlsx TSV_OUT=full_cohort.tsv
```
