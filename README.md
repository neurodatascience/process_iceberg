# ICEBERG → Neurobagel

Pipeline for extracting and annotating ICEBERG cohort data into a Neurobagel graph node.

---

## Prerequisites

- Python 3.11+
- [bagel-cli](https://neurobagel.org/user_guide/cli/) installed and on your `PATH`
- Docker with the Compose plugin

---

## Setup

Copy your REDCap Excel export into `input/` — exactly one file:

```bash
cp /path/to/iceberg_redcap_export.xlsx input/
```

---

## Step-by-step

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Extract phenotypic and imaging TSVs from the Excel file

```bash
make all
```

Produces:
- `output/iceberg_neurobagel_phenotype.tsv` — participant × variable table
- `output/iceberg_neurobagel_imaging.tsv` — one row per acquired imaging modality

### 3. Generate the `.jsonld` file

```bash
make bagel
```

Runs `bagel pheno` (annotates the phenotype TSV using `static/iceberg_neurobagel_synthetic_annotated.json` and `static/iceberg_dataset_description.json`) then `bagel bids` (folds in the imaging table). Produces `output/iceberg_neurobagel.jsonld`.

### 4. Deploy to the Neurobagel node

```bash
make deploy
```

Copies `output/iceberg_neurobagel.jsonld` into `neurobagel/data/` and starts the node with `docker compose up -d`.

---

## Full pipeline (all steps at once)

```bash
make run
```

Equivalent to `make all && make bagel && make deploy`.

---

## Directory layout

```
input/     Place the REDCap Excel export here (exactly one .xlsx/.xls file)
static/    Pre-generated files: YAML mapping, annotated data dictionary, dataset description
scripts/   Python extraction and table-building scripts
output/    Generated TSVs and JSONLD files
neurobagel/ Neurobagel node (git subtree) — data/ is the JSONLD target directory
```

---

## Makefile targets

| Target | Action |
|--------|--------|
| `make run` | Full pipeline: extract TSVs → generate JSONLD → deploy |
| `make all` | Extract phenotype TSV + imaging TSV |
| `make extract` | Phenotype TSV only |
| `make imaging` | Imaging TSV only (requires `make extract` first) |
| `make bagel` | Generate JSONLD from TSVs + data dictionary |
| `make deploy` | Copy JSONLD to `neurobagel/data/` and start Docker node |
| `make synthetic` | Generate synthetic test TSV for annotation testing |
| `make dictionary` | Generate long-form data dictionary TSV |
| `make clean` | Remove all generated output files |
