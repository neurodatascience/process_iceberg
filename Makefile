PYTHON  := python3

# ── Input (auto-detect single .xlsx in input/) ─────────────────────────────────
EXCEL_FILES := $(wildcard input/*.xlsx)
n_excel     := $(words $(EXCEL_FILES))
ifeq ($(n_excel),0)
  $(error No Excel file found in input/. Copy your .xlsx file there.)
endif
ifneq ($(n_excel),1)
  $(error Multiple Excel files found in input/ ($(EXCEL_FILES)). Leave only one.)
endif
EXCEL := $(firstword $(EXCEL_FILES))

# ── Static files ───────────────────────────────────────────────────────────────
MAPPING       := static/iceberg_neurobagel_mapping.yaml
ANNOTATED_DICT := static/iceberg_neurobagel_synthetic_annotated.json
DATASET_DESC  := static/iceberg_dataset_description.json

# ── Outputs ────────────────────────────────────────────────────────────────────
TSV_OUT       := output/iceberg_neurobagel_phenotype.tsv
IMAGING_OUT   := output/iceberg_neurobagel_imaging.tsv
SYNTHETIC_OUT := output/iceberg_neurobagel_synthetic.tsv
DICT_OUT      := output/iceberg_data_dictionary.tsv
JSONLD_PHENO  := output/iceberg_neurobagel_pheno.jsonld
JSONLD_OUT    := output/iceberg_neurobagel.jsonld

# ── Default target ─────────────────────────────────────────────────────────────
.PHONY: all
all: extract imaging

# ── Help ───────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "ICEBERG → Neurobagel extraction pipeline"
	@echo ""
	@echo "  make extract     Run phenotype extraction → $(TSV_OUT)"
	@echo "  make imaging     Build imaging table → $(IMAGING_OUT)"
	@echo "  make synthetic   Generate synthetic test TSV → $(SYNTHETIC_OUT)"
	@echo "  make dictionary  Generate data dictionary → $(DICT_OUT)"
	@echo "  make bagel-pheno Annotate phenotype TSV → $(JSONLD_PHENO)"
	@echo "  make bagel-bids  Add imaging data → $(JSONLD_OUT)"
	@echo "  make bagel       bagel-pheno + bagel-bids"
	@echo "  make all         extract + imaging"
	@echo "  make clean       Remove generated output files"
	@echo "  make help        Show this message"
	@echo ""
	@echo "Input Excel detected: $(EXCEL)"
	@echo ""

# ── Extraction ─────────────────────────────────────────────────────────────────
.PHONY: extract
extract:
	$(PYTHON) scripts/extract_neurobagel_tsv.py \
		--mapping $(MAPPING) \
		--excel   $(EXCEL)   \
		--output  $(TSV_OUT)

# ── Imaging table ─────────────────────────────────────────────────────────────
.PHONY: imaging
imaging:
	$(PYTHON) scripts/build_imaging_table.py \
		--mapping $(MAPPING) \
		--tsv     $(TSV_OUT) \
		--output  $(IMAGING_OUT)

# ── Synthetic test data ────────────────────────────────────────────────────────
.PHONY: synthetic
synthetic:
	$(PYTHON) scripts/generate_synthetic_tsv.py \
		--mapping      $(MAPPING) \
		--tsv-template $(TSV_OUT) \
		--output       $(SYNTHETIC_OUT)

# ── Data dictionary ────────────────────────────────────────────────────────────
.PHONY: dictionary
dictionary:
	$(PYTHON) scripts/generate_data_dictionary.py \
		--mapping      $(MAPPING) \
		--tsv-template $(TSV_OUT) \
		--output       $(DICT_OUT)

# ── Bagel phenotype annotation ─────────────────────────────────────────────────
.PHONY: bagel-pheno
bagel-pheno:
	bagel pheno \
		--pheno               $(TSV_OUT) \
		--dictionary          $(ANNOTATED_DICT) \
		--dataset-description $(DATASET_DESC) \
		--output              $(JSONLD_PHENO)

# ── Bagel imaging integration ──────────────────────────────────────────────────
.PHONY: bagel-bids
bagel-bids: bagel-pheno
	bagel bids \
		--jsonld-path $(JSONLD_PHENO) \
		--bids-table  $(IMAGING_OUT) \
		--output      $(JSONLD_OUT) \
		--overwrite

.PHONY: bagel
bagel: bagel-bids

# ── Clean ──────────────────────────────────────────────────────────────────────
.PHONY: clean
clean:
	rm -f $(TSV_OUT) $(IMAGING_OUT) $(SYNTHETIC_OUT) $(DICT_OUT) $(JSONLD_PHENO) $(JSONLD_OUT)
	@echo "Cleaned."
