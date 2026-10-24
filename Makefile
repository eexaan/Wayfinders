# Wayfinders build + verification.
#
#   make setup    create .venv and install dependencies (once)
#   make data     rebuild every derived table from the raw inputs
#   make figures  rebuild F1..F7 into docs/figures/
#   make gtfs     rebuild the GTFS feed
#   make reroute  rebuild the reroute network and its proof run
#   make check    verify the committed outputs against the raw sources
#   make web      build the dashboard (React app in web/) into web/dist
#   make serve    build the dashboard and serve it on http://localhost:4444
#   make deploy   build and rsync web/dist to a static webroot
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
OWNER   ?= www-data:www-data

.PHONY: all setup data figures gtfs reroute check test clean validate-gtfs web serve deploy

all: data figures gtfs reroute check test

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

# The reroute chain, in order: the population surface feeds the stop choice, the
# stop choice feeds the network, and the network feeds the proof run. The headless
# simulation is the SAME engine the browser animates (web/src/sim/engine.mjs), so
# this target needs node as well as python.
reroute:
	$(PY) $(BUILD)/build_population.py
	$(PY) $(BUILD)/build_reroute_network.py
	cd web && node scripts/run-sim.mjs

check:
	$(PY) $(BUILD)/verify_claims.py

# The dashboard is the React app in web/. Vite bundles it to web/dist, and
# scripts/sync-data.mjs copies the frozen data contract from dashboard/data/
# into the bundle first, so the built site makes no network calls at runtime.
# Needs Node 20+ and a first `npm ci` (network) — everything else is offline.
web:
	cd web && npm ci --silent && npm run build

serve: web
	cd web/dist && python3 -m http.server 4444

# Deploy the built bundle to a static webroot. Replaces the directory contents.
#   make deploy HOST=root@<origin> DEST=/var/www/wayfinders
deploy: web
	@test -n "$(HOST)" || { echo "usage: make deploy HOST=user@server DEST=/var/www/wayfinders"; exit 1; }
	@test -n "$(DEST)" || { echo "usage: make deploy HOST=user@server DEST=/var/www/wayfinders"; exit 1; }
	ssh "$(HOST)" 'mkdir -p "$(DEST)"'
	rsync -a --delete web/dist/ "$(HOST):$(DEST)/"
	ssh "$(HOST)" 'chown -R $(OWNER) "$(DEST)" && find "$(DEST)" -type d -exec chmod 755 {} + && find "$(DEST)" -type f -exec chmod 644 {} +'

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
