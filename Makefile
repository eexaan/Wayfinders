# Wayfinders build + verification.
#
#   make setup    create .venv and install dependencies (once)
#   make data     rebuild every derived table from the raw inputs
#   make figures  rebuild F1..F7 into docs/figures/
#   make gtfs     rebuild the GTFS feed
#   make check    verify the committed outputs against the raw sources
#   make serve    serve the dashboard on http://localhost:8000
#   make test     run the unit tests (the reallocator guards)
#   make all      data + figures + gtfs + check + test
#   make clean    remove build caches only, never data/
#
# The order in `data` is load-bearing: build_stop_demand.py reads what
# build_data.py writes, and rebuilds the scenarios afterwards so the KPI table
# and demand_supply_gap.csv cannot disagree.

PY      := .venv/bin/python
BUILD   := dashboard/build
DATAOUT := dashboard/data

.PHONY: all setup data figures gtfs check test clean validate-gtfs

all: data figures gtfs check test

setup:
	python3 -m venv .venv
	$(PY) -m pip install --quiet --upgrade pip || true
	$(PY) -m pip install --quiet -r requirements.txt || 	  uv pip install --python $(PY) -r requirements.txt
	@$(PY) -c "import pandas, numpy, openpyxl, matplotlib; \
	  print('ready:', '$(PY)')" || \
	  { echo "install incomplete: run 'python3 -m pip install -r requirements.txt'"; exit 1; }

# Each step runs separately so a failure names the script that broke.
data:
	$(PY) $(BUILD)/build_data.py
	$(PY) $(BUILD)/build_stop_demand.py
	$(PY) $(BUILD)/build_validation.py
	$(PY) $(BUILD)/build_schedule_crosscheck.py

figures:
	$(PY) $(BUILD)/build_figures.py

gtfs:
	$(PY) $(BUILD)/build_gtfs.py

check:
	$(PY) $(BUILD)/verify_claims.py

# The dashboard is a static site; fetch() is blocked over file://, so it has to
# be served. No build step, no dependencies.
serve:
	@test -f dashboard/index.html || \
	  { echo "dashboard/index.html is not in this checkout — see docs/DASHBOARD_SPEC.md §0"; exit 1; }
	cd dashboard && python3 -m http.server 8000

test:
	$(PY) -m pytest tests -q

# Needs java and the validator jar (not committed: ~40 MB).
#   curl -L -o gtfs-validator.jar \
#     https://github.com/MobilityData/gtfs-validator/releases/download/v6.0.0/gtfs-validator-6.0.0-cli.jar
validate-gtfs: gtfs
	java -jar gtfs-validator.jar \
	  -i data/derived/rtl_greater_male_gtfs.zip \
	  -o /tmp/gtfs-report

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	@echo "removed __pycache__ directories"
