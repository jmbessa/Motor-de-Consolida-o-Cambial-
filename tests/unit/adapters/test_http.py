"""Testes do cliente HTTP resiliente."""

from decimal import Decimal

import httpx
import pytest

from motor_cambial.adapters.outbound.http import obter_json
from motor_cambial.domain.errors import FonteIndisponivel, RespostaInvalida


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_sucesso_parseia_numeros_como_decimal():
    def handler(request):
        return httpx.Response(200, json={"taxa": 5.0599})

    payload = obter_json(_client(handler), "https://x/y")
    assert payload["taxa"] == Decimal("5.0599")
    assert isinstance(payload["taxa"], Decimal)


def test_retenta_em_5xx_e_depois_falha():
    chamadas = {"n": 0}

    def handler(request):
        chamadas["n"] += 1
        return httpx.Response(500, text="erro")

    with pytest.raises(FonteIndisponivel):
        obter_json(_client(handler), "https://x/y", max_retries=2)
    assert chamadas["n"] == 3  # 1 + 2 retries


def test_retenta_em_timeout_e_depois_falha():
    chamadas = {"n": 0}

    def handler(request):
        chamadas["n"] += 1
        raise httpx.ConnectTimeout("timeout", request=request)

    with pytest.raises(FonteIndisponivel):
        obter_json(_client(handler), "https://x/y", max_retries=1)
    assert chamadas["n"] == 2


def test_4xx_nao_retenta_e_retorna_corpo():
    chamadas = {"n": 0}

    def handler(request):
        chamadas["n"] += 1
        return httpx.Response(404, json={"message": "not found"})

    payload = obter_json(_client(handler), "https://x/y", max_retries=2)
    assert payload == {"message": "not found"}
    assert chamadas["n"] == 1  # não retentou


def test_corpo_nao_json_levanta_resposta_invalida():
    def handler(request):
        return httpx.Response(200, text="<html>não-json</html>")

    with pytest.raises(RespostaInvalida):
        obter_json(_client(handler), "https://x/y")
