# Ezermalas e-pakalpojums "Iesniegumi" · atjaunošanas mācības. Saraksts: make help
SHELL := /bin/bash
PY ?= python
DRILL := $(PY) -m drill
export PYTHONIOENCODING := utf-8

.DEFAULT_GOAL := help
.PHONY: help status katastrofa backup-list replicate reset run test llm

help: ## Parāda komandas
	@awk -F ':.*## ' '/^[a-zA-Z_%-]+:.*## / {printf "  make %-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

status: ## Sistēmas stāvoklis: portāls, serveri, iesniegumi, triāža
	@$(DRILL) status

katastrofa: ## Sāk jūsu grupas katastrofu: make katastrofa GROUP=1 (1, 2, 3 vai 4)
	@$(DRILL) katastrofa --group "$(GROUP)"

backup-list: ## Rezerves kopiju saraksts: laiks, izmērs, kontrolsumma, žurnāls
	@$(DRILL) backup-list

replicate: ## Sinhronizē rezerves serveri ar galveno (automātiski ik pēc 15 min)
	@$(DRILL) replicate

reset: ## Sākuma stāvoklis pirms katastrofas (visu izveido no jauna)
	@$(DRILL) reset

run: ## Palaiž portālu (ports 8000: /ui un /ui/darbinieks.html)
	$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

test: ## Palaiž testus
	@$(PY) -m pytest -q

llm:
	@$(DRILL) llm --mode "$(MODE)"
