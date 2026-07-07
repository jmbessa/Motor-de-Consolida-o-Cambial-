"""Testes do client Frankfurter (com httpx.MockTransport, sem rede real)."""

from datetime import date
from decimal import Decimal

import httpx
import pytest

from motor_cambial.adapters.outbound.frankfurter.client import FrankfurterProvider
from motor_cambial.domain.enums import Fonte, Moeda
from motor_cambial.domain.errors import MoedaNaoSuportadaPelaFonte

_BODY_OK = (
    '{"amount":1.0,"base":"USD","start_date":"2026-06-01","end_date":"2026-06-08",'
    '"rates":{"2026-06-05":{"BRL":5.0599},"2026-06-08":{"BRL":5.1432}}}'
)


def _provider(handler) -> FrankfurterProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    return FrankfurterProvider(client=client, base_url="https://api.frankfurter.app")


def test_monta_url_de_intervalo_e_normaliza():
    capturado = {}

    def handler(request):
        capturado["url"] = str(request.url)
        return httpx.Response(200, text=_BODY_OK)

    provider = _provider(handler)
    cotacoes = provider.buscar_cotacoes(Moeda.USD, date(2026, 6, 1), date(2026, 6, 8))

    assert provider.fonte is Fonte.FRANKFURTER
    assert "2026-06-01..2026-06-08" in capturado["url"]
    assert "from=USD" in capturado["url"] and "to=BRL" in capturado["url"]
    assert {c.data_referencia for c in cotacoes} == {date(2026, 6, 5), date(2026, 6, 8)}
    assert cotacoes[0].taxa_compra == Decimal("5.0599")


def test_moeda_nao_encontrada_propaga_erro():
    def handler(request):
        return httpx.Response(404, json={"message": "not found"})

    with pytest.raises(MoedaNaoSuportadaPelaFonte):
        _provider(handler).buscar_cotacoes(Moeda.USD, date(2026, 6, 1), date(2026, 6, 8))
