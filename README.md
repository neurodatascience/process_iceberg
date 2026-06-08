# ICEBERG → Neurobagel

This repo contains a pipeline to
- extracting information from the ICEBERG RedCap dump (excel file)
- combine the information with a pre-generated data dictionary (`static/iceberg_neurobagel_synthetic_annotated.json`)
- generate the ICEBERG Neurobagel graph file
- launch a local Neurobagel query portal that can query ICEBERG and also the ENIGMA-PD nodes

---

## Prerequisites

- Python 3.11+ (ideally a virtual environment)
- Docker with the Compose plugin
- The full ICEBERG RedCap dump as a Excel file (.xlsx)

---

## Preparation

> [!NOTE]  
> If you want to change how the ICEBERG dataset will appear in Neurobagel,
> edit the `static/iceberg_dataset_description.json` file.
> Refer to the [Neurobagel docs](https://neurobagel.org/user_guide/dataset_description/) for details.

### 1. Copy the REDCap Excel file

Copy your REDCap Excel export into `input/` — exactly one file:

```bash
cp /path/to/iceberg_redcap_export.xlsx input/
```

look at `static/iceberg_neurobagel_mapping.yaml` to see the expected Excel sheet and column names

### 2. Install the dependencies

```bash
pip install -r requirements.txt
```

---

## Quickstart

```bash
make run
```

This should launch a Neurobagel query portal at
[http://localhost:3000](http://localhost:3000).


## Step-by-step

### 1. Extract phenotypic and imaging TSVs from the Excel file

```bash
make all
```

Produces:
- `output/iceberg_neurobagel_phenotype.tsv` — participant × variable table
- `output/iceberg_neurobagel_imaging.tsv` — one row per acquired imaging modality

### 2. Generate the `.jsonld` file

```bash
make bagel
```

Runs `bagel pheno` (annotates the phenotype TSV using `static/iceberg_neurobagel_synthetic_annotated.json` and `static/iceberg_dataset_description.json`) then `bagel bids` (folds in the imaging table). Produces `output/iceberg_neurobagel.jsonld`.

### 3. Deploy to the Neurobagel node

```bash
make deploy
```

Removes all existing `.jsonld` files from `neurobagel/data/`, copies `output/iceberg_neurobagel.jsonld` there, then starts the node with `docker compose up -d`.

> [!WARNING]
> `make deploy` clears the entire `neurobagel/data/` directory before copying. If you have placed additional `.jsonld` files there manually, they will be deleted.

### 4. Shut down the node

```bash
make stop
```

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
| `make stop` | Shut down the Docker node |
| `make synthetic` | Generate synthetic test TSV for annotation testing |
| `make dictionary` | Generate long-form data dictionary TSV |
| `make clean` | Remove all generated output files |
