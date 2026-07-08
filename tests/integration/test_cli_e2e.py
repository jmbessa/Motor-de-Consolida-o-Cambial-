"""Teste de integração ponta a ponta da CLI (opt-in: -m integration + rede + MySQL).

Roda a CLI real contra as APIs reais e o MySQL do container (mesmo padrão
das integrações da Fatia 6a) — a prova executável do "modo live demonstrável"
e da persistência real de ponta a ponta.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from motor_cambial.adapters.inbound.cli.app import app

pytestmark = pytest.mark.integration

runner = CliRunner()


@pytest.fixture(autouse=True)
def _requer_db(monkeypatch):
    if not os.environ.get("MOTOR_TEST_DB_URL"):
        pytest.skip("MOTOR_TEST_DB_URL não definido (requer MySQL da Fatia 6b)")
    monkeypatch.setenv("MOTOR_DB_HOST", "127.0.0.1")


def test_cli_ponta_a_ponta_contra_apis_e_mysql_reais(tmp_path):
    # Data recente o bastante para cair dentro da janela de fallback default (7 dias).
    data_referencia = date.today() - timedelta(days=5)
    saida = tmp_path / "saida.json"
    resultado = runner.invoke(
        app,
        [
            "--arquivo", "data/exposicoes.json",
            "--data", data_referencia.isoformat(),
            "--saida", str(saida),
        ],
    )
    assert resultado.exit_code == 0, resultado.output
    assert saida.exists()
    assert "Motor de Consolidação Cambial" in resultado.output
