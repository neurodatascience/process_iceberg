# ── Paths ──────────────────────────────────────────────────────────────────────
# uv may live outside PATH in some container environments
export PATH := /home/node/.local/bin:$(PATH)

VENV    := .venv
PYTHON  := $(VENV)/bin/python3
UV      := uv

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
	@echo "  make install   Create .venv and install Python dependencies"
	@echo "  make extract   Run extraction → $(TSV_OUT)"
	@echo "  make all       install + extract (default)"
	@echo "  make clean     Remove .venv and generated output files"
	@echo "  make help      Show this message"
	@echo ""
	@echo "Override defaults:"
	@echo "  make extract EXCEL=path/to/file.xlsx"
	@echo "  make extract MAPPING=my_mapping.yaml"
	@echo "  make extract TSV_OUT=my_output.tsv"
	@echo ""

# ── Virtual environment ─────────────────────────────────────────────────────────
$(VENV):
	$(UV) venv $(VENV)

# ── Dependencies ───────────────────────────────────────────────────────────────
.PHONY: install
install: $(VENV)
	$(UV) pip install --python $(PYTHON) -r requirements.txt

# ── Extraction ─────────────────────────────────────────────────────────────────
.PHONY: extract
extract: install
	$(PYTHON) extract_neurobagel_tsv.py \
		--mapping  $(MAPPING) \
		--excel    $(EXCEL)   \
		--output   $(TSV_OUT)

# ── Clean ──────────────────────────────────────────────────────────────────────
.PHONY: clean
clean:
	rm -rf $(VENV) $(TSV_OUT)
	@echo "Cleaned."
