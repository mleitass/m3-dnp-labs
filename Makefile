# Ezermalas e-pakalpojums "Iesniegumi" · atjaunošanas mācības. Saraksts: make help
SHELL := /bin/bash
PY ?= python
DRILL := $(PY) -m drill
export PYTHONIOENCODING := utf-8
# Kļūdas ziņojumu parāda pati komanda; make to neatkārto. STRICT=1 atgriež kļūdas kodu.
OK = || [ -z "$(STRICT)" ]

.DEFAULT_GOAL := help
.PHONY: help status katastrofa backup-list restore failover replicate verify \
	triage triage-config reset run test llm

help: ## Parāda komandas
	@awk -F ':.*## ' '/^[a-zA-Z_%-]+:.*## / {printf "  make %-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

status: ## Sistēmas stāvoklis: portāls, serveri, iesniegumi, triāža
	@$(DRILL) status $(OK)

katastrofa: ## Sāk jūsu grupas katastrofu: make katastrofa GROUP=1 (1, 2, 3 vai 4)
	@$(DRILL) katastrofa --group "$(GROUP)" $(OK)

backup-list: ## Rezerves kopiju saraksts: laiks, izmērs, kontrolsumma, žurnāls
	@$(DRILL) backup-list $(OK)

restore: ## Atjauno galveno serveri no kopijas: make restore BACKUP=<ID vai D-1>
	@$(DRILL) restore --backup "$(BACKUP)" $(OK)

failover: ## Pārslēdz servisu uz rezerves serveri
	@$(DRILL) failover $(OK)

replicate: ## Sinhronizē rezerves serveri ar galveno (automātiski ik pēc 15 min)
	@$(DRILL) replicate $(OK)

verify: ## Pārbauda rezultātu: zaudētie dati (RPO), pielikumi, triāža
	@$(DRILL) verify $(OK)

triage: ## Triāžas režīms: make triage MODE=manual (Kanceleja) vai MODE=auto
	@$(DRILL) triage --mode "$(MODE)" $(OK)

reset: ## Sākuma stāvoklis pirms katastrofas (visu izveido no jauna)
	@$(DRILL) reset $(OK)

run: ## Palaiž portālu (ports 8000: /ui un /ui/darbinieks.html)
	$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

test: ## Palaiž testus
	@$(PY) -m pytest -q

# Bez apraksta sarakstā make help (izmanto pēc kartītes vai pasniedzēja norādes):
triage-config:
	@$(DRILL) triage-config $(OK)

llm:
	@$(DRILL) llm --mode "$(MODE)" $(OK)
