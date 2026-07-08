# Makefile — porta de entrada única do projeto.
#
# Alvos de DESENVOLVIMENTO usam o venv local (rápido, para o ciclo TDD).
# Alvos de EXECUÇÃO/ENTREGA usam Docker Compose (backend + frontend + MySQL) e
# são implementados na fatia de infraestrutura — por ora são placeholders
# explícitos, para não fingir comportamento inexistente.

# Interpretador do venv — o layout muda entre Windows e POSIX.
ifeq ($(OS),Windows_NT)
VENV_PY := .venv/Scripts/python.exe
else
VENV_PY := .venv/bin/python
endif

.DEFAULT_GOAL := help
.PHONY: help install test test-integration run run-live up down logs migrate seed clean

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

# --- Execução / entrega (Docker Compose) ---

COMPOSE := docker compose
# Alvos rodados do host (venv) contra o container publicam o MySQL em 127.0.0.1
# (o default MOTOR_DB_HOST=db só resolve na rede interna do Compose — Fatia 8).
HOST_DB := MOTOR_DB_HOST=127.0.0.1
TEST_DB_URL := mysql+pymysql://motor:motor@127.0.0.1:3306/motor_cambial

up: ## Sobe o MySQL e espera ficar healthy
	$(COMPOSE) up -d --wait db

down: ## Derruba o container (mantém o volume de dados)
	$(COMPOSE) down

logs: ## Acompanha os logs do MySQL
	$(COMPOSE) logs -f db

migrate: up ## Sobe o MySQL (se preciso) e aplica o schema (criar_schema)
	$(HOST_DB) $(VENV_PY) -m motor_cambial.adapters.outbound.persistence.migrate

test-integration: up ## Sobe o MySQL (se preciso) e roda os testes de integração
	MOTOR_TEST_DB_URL=$(TEST_DB_URL) $(VENV_PY) -m pytest -m integration

seed: ## Confirma a presença da massa de dados de exemplo (data/exposicoes.json)
	@test -f data/exposicoes.json && echo "data/exposicoes.json presente." || \
		(echo "data/exposicoes.json ausente." && exit 1)

run: migrate ## Sobe o MySQL, aplica o schema e roda a CLI uma vez com os defaults (cache-first)
	$(HOST_DB) $(VENV_PY) -m motor_cambial.adapters.inbound.cli.app

run-live: migrate ## Como `run`, mas consulta PTAX e Frankfurter ao vivo (ignora o cache)
	$(HOST_DB) $(VENV_PY) -m motor_cambial.adapters.inbound.cli.app --live

clean: ## Derruba o container COM o volume e limpa caches locais
	$(COMPOSE) down -v
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
