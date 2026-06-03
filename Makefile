PYTHON  := python3

EXCEL   := 2023_04_05_Gel_Iceberg_patient1.xlsx
MAPPING := iceberg_neurobagel_mapping.yaml
TSV_OUT := iceberg_neurobagel_phenotype.tsv

# ── Default target ─────────────────────────────────────────────────────────────
.PHONY: all
all: extract

# ── Help ───────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "ICEBERG → Neurobagel extraction pipeline"
	@echo ""
	@echo "  make extract   Run extraction → $(TSV_OUT)"
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

# ── Clean ──────────────────────────────────────────────────────────────────────
.PHONY: clean
clean:
	rm -f $(TSV_OUT)
	@echo "Cleaned."
