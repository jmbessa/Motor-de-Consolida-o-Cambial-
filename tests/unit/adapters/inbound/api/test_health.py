"""Testes do scaffold da API (health + CORS), sem rede/DB."""

from fastapi.testclient import TestClient

from motor_cambial.adapters.inbound.api.app import criar_app


def test_health_retorna_ok():
    client = TestClient(criar_app())
    resposta = client.get("/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_cors_header_presente_para_requisicao_com_origin():
    client = TestClient(criar_app())
    resposta = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert resposta.headers.get("access-control-allow-origin") == "*"
