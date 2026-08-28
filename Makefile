PY := venv/bin/python
PIP := venv/bin/pip
RUFF := venv/bin/ruff

.PHONY: setup test lint engine-us engine-india plan execute-dry export dashboard deploy \
	monitor-install monitor-status replay report

setup:
	python3 -m venv venv
	$(PIP) install -r requirements.txt -r requirements-dev.txt
	cd dashboard && npm ci

test:
	$(PY) -m pytest -p no:cacheprovider

lint:
	$(RUFF) check quantshield tests

engine-us:
	$(PY) -m quantshield.engine --market us

engine-india:
	$(PY) -m quantshield.engine --market india

plan:
	$(PY) -m quantshield.live.planner --no-notify

execute-dry:
	$(PY) -m quantshield.live.executor --dry-run

export:
	$(PY) -m quantshield.live.export

dashboard:
	cd dashboard && npm run build

deploy:
	scripts/deploy_dashboard.sh

monitor-install:
	scripts/launchd.sh monitor install

monitor-status:
	scripts/launchd.sh monitor status

replay:
	$(PY) -m quantshield.intraday.replay

report:
	cd docs && for pass in 1 2 3; do pdflatex -interaction=nonstopmode -halt-on-error research_report.tex >/dev/null; done
	cd docs && rm -f research_report.aux research_report.log research_report.out research_report.toc \
		research_report.fls research_report.fdb_latexmk research_report.synctex.gz
	cp docs/research_report.pdf dashboard/public/research_report.pdf
