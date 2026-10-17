# Ezermalas e-pakalpojums "Iesniegumi" · komandas. Saraksts: make help
SHELL := /bin/bash
PY ?= python

.PHONY: help run test

help: ## Parāda komandas
	@awk -F ':.*## ' '/^[a-zA-Z_%-]+:.*## / {printf "  make %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

run: ## Palaiž portālu (ports 8000: /ui un /docs)
	$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

test: ## Palaiž testus
	$(PY) -m pytest -q
