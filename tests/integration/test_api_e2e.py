"""Integração ponta a ponta da API (opt-in: -m integration + rede + MySQL).

Mesmo padrão de tests/integration/test_cli_e2e.py: requer MOTOR_TEST_DB_URL e
o MySQL da Fatia 6b; força MOTOR_DB_HOST=127.0.0.1 para o venv do host.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from motor_cambial.adapters.inbound.api.app import criar_app

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _requer_db(monkeypatch):
    if not os.environ.get("MOTOR_TEST_DB_URL"):
        pytest.skip("MOTOR_TEST_DB_URL não definido (requer MySQL da Fatia 6b)")
    monkeypatch.setenv("MOTOR_DB_HOST", "127.0.0.1")


def test_api_ponta_a_ponta_post_e_get():
    client = TestClient(criar_app())
    data_ref = (date.today() - timedelta(days=5)).isoformat()
    corpo = {
        "exposicoes": [
            {"id": "1", "tipo": "payable", "moeda": "USD", "valor": "125000",
             "vencimento": "2026-06-05"}
        ],
        "data_referencia": data_ref,
        "modo_live": True,
    }
    r = client.post("/consolidacoes", json=corpo)
    assert r.status_code == 200, r.text
    hash_conjunto = r.json()["hash_conjunto"]

    r2 = client.get(f"/consolidacoes/{data_ref}/{hash_conjunto}")
    assert r2.status_code == 200
    assert r2.json()["hash_conjunto"] == hash_conjunto
