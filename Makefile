# Makefile — porta de entrada única do projeto.
#
# Alvos de DESENVOLVIMENTO usam o venv local (rápido, para o ciclo TDD).
# Alvos de EXECUÇÃO combinam Docker Compose (MySQL, e no caminho do dashboard
# também backend+frontend) com a aplicação (venv, para o caminho da CLI).

COMPOSE := docker compose
TEST_DB_URL := mysql+pymysql://motor:motor@127.0.0.1:3306/motor_cambial

# Interpretador do venv e variáveis de env por comando — o layout muda entre
# Windows e POSIX.
#
# Sem Git Bash/WSL no PATH, o make resolve cmd.exe como shell de receita, o
# que quebra de duas formas: (1) `VAR=valor comando` (prefixo de env var,
# sintaxe POSIX) falha com "'VAR' não é reconhecido..."; (2) `$(VENV_PY)`
# com barra normal (`.venv/Scripts/python.exe`) falha com "'.venv' não é
# reconhecido..." — cmd.exe só resolve o COMANDO principal (não argumentos)
# com contrabarra. Por isso os alvos que rodam Python forçam `SHELL :=
# cmd.exe` (sempre presente no Windows) e usam `\` + `set VAR=valor&&` —
# determinístico, em vez de depender de qual shell o make detectar.
ifeq ($(OS),Windows_NT)
VENV_PY := .venv\Scripts\python.exe
HOST_DB := set MOTOR_DB_HOST=127.0.0.1&&
SET_TEST_DB_URL := set MOTOR_TEST_DB_URL=$(TEST_DB_URL)&&
RECIPE_SHELL := cmd.exe
else
VENV_PY := .venv/bin/python
HOST_DB := MOTOR_DB_HOST=127.0.0.1
SET_TEST_DB_URL := MOTOR_TEST_DB_URL=$(TEST_DB_URL)
RECIPE_SHELL := $(SHELL)
endif

.DEFAULT_GOAL := help
.PHONY: help install test test-integration run run-cli run-live run-dashboard api up down logs migrate seed clean

help: ## Lista os alvos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

# --- Desenvolvimento (venv local) ---

install: ## Cria o venv e instala as dependências (modo dev)
	python -m venv .venv
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -e ".[dev]"

test: ## Roda a suíte de testes
	$(VENV_PY) -m pytest

# --- Execução: CLI (venv + só o MySQL em container — não usa a API) ---
#
# A CLI é um adapter separado que chama a lógica de negócio direto, em
# processo — não faz requisição HTTP à API. Por isso só precisa do MySQL.

install test migrate run run-live api test-integration: SHELL := $(RECIPE_SHELL)

up: ## Sobe o MySQL e espera ficar healthy
	$(COMPOSE) up -d --wait db

down: ## Derruba todos os containers (mantém o volume de dados)
	$(COMPOSE) down

logs: ## Acompanha os logs do MySQL
	$(COMPOSE) logs -f db

migrate: up ## Sobe o MySQL (se preciso) e aplica o schema (criar_schema)
	$(HOST_DB) $(VENV_PY) -m motor_cambial.adapters.outbound.persistence.migrate

test-integration: up ## Sobe o MySQL (se preciso) e roda os testes de integração
	$(SET_TEST_DB_URL) $(VENV_PY) -m pytest -m integration

seed: ## Confirma a presença da massa de dados de exemplo (data/exposicoes.json)
	@test -f data/exposicoes.json && echo "data/exposicoes.json presente." || \
		(echo "data/exposicoes.json ausente." && exit 1)

run: migrate ## CLI: sobe o MySQL, aplica o schema e consolida uma vez (cache-first)
	$(HOST_DB) $(VENV_PY) -m motor_cambial.adapters.inbound.cli.app

run-cli: run ## Alias de `run` — nome simétrico a `run-dashboard`

run-live: migrate ## Como `run`, mas consulta PTAX e Frankfurter ao vivo (ignora o cache)
	$(HOST_DB) $(VENV_PY) -m motor_cambial.adapters.inbound.cli.app --live

api: migrate ## Serve só a API do venv (dev), sem o container do backend
	$(HOST_DB) $(VENV_PY) -m uvicorn motor_cambial.adapters.inbound.api.app:app --port 8000

# --- Execução: Dashboard (db + API + frontend, tudo em containers) ---

run-dashboard: ## Dashboard: sobe db + API + frontend em containers (:8080, API :8000)
	$(COMPOSE) up -d --build --wait

clean: ## Derruba os containers COM o volume e limpa caches locais
	$(COMPOSE) down -v
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
