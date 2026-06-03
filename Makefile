PYTHON  := python3

EXCEL         := 2023_04_05_Gel_Iceberg_patient1.xlsx
MAPPING       := iceberg_neurobagel_mapping.yaml
TSV_OUT       := iceberg_neurobagel_phenotype.tsv
IMAGING_OUT   := iceberg_neurobagel_imaging.tsv
SYNTHETIC_OUT := iceberg_neurobagel_synthetic.tsv

# ── Default target ─────────────────────────────────────────────────────────────
.PHONY: all
all: extract imaging

# ── Help ───────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "ICEBERG → Neurobagel extraction pipeline"
	@echo ""
	@echo "  make extract    Run phenotype extraction → $(TSV_OUT)"
	@echo "  make imaging    Build imaging table → $(IMAGING_OUT)"
	@echo "  make synthetic  Generate synthetic test TSV → $(SYNTHETIC_OUT)"
	@echo "  make all        extract + imaging"
	@echo "  make clean     Remove generated output files"
	@echo "  make help      Show this message"
	@echo ""
	@echo "Override defaults:"
	@echo "  make extract PYTHON=path/to/python"
	@echo "  make extract EXCEL=path/to/file.xlsx"
	@echo "  make extract MAPPING=my_mapping.yaml"
	@echo "  make extract TSV_OUT=my_output.tsv"
	@echo ""

# ── Extraction ─────────────────────────────────────────────────────────────────
.PHONY: extract
extract:
	$(PYTHON) extract_neurobagel_tsv.py \
		--mapping  $(MAPPING) \
		--excel    $(EXCEL)   \
		--output   $(TSV_OUT)

# ── Imaging table ─────────────────────────────────────────────────────────────
.PHONY: imaging
imaging:
	$(PYTHON) build_imaging_table.py \
		--mapping $(MAPPING) \
		--tsv     $(TSV_OUT) \
		--output  $(IMAGING_OUT)

# ── Synthetic test data ────────────────────────────────────────────────────────
.PHONY: synthetic
synthetic:
	$(PYTHON) generate_synthetic_tsv.py \
		--mapping      $(MAPPING) \
		--tsv-template $(TSV_OUT) \
		--output       $(SYNTHETIC_OUT)

# ── Clean ──────────────────────────────────────────────────────────────────────
.PHONY: clean
clean:
	rm -f $(TSV_OUT) $(IMAGING_OUT) $(SYNTHETIC_OUT)
	@echo "Cleaned."
