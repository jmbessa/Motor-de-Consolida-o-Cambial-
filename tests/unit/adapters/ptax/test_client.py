"""Testes do client PTAX (com httpx.MockTransport, sem rede real)."""

from datetime import date
from decimal import Decimal

import httpx
import pytest

from motor_cambial.adapters.outbound.ptax.client import PtaxProvider
from motor_cambial.domain.enums import Fonte, Moeda
from motor_cambial.domain.errors import RespostaInvalida

_BASE = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"
_VALUE_USD = (
    '{"value":[{"cotacaoCompra":5.12380,"cotacaoVenda":5.12440,'
    '"dataHoraCotacao":"2026-06-05 13:03:38.306"}]}'
)
_VALUE_EUR = (
    '{"value":[{"cotacaoCompra":5.90880,"cotacaoVenda":5.91000,'
    '"dataHoraCotacao":"2026-06-05 13:03:38.306","tipoBoletim":"Fechamento"}]}'
)


def _provider(handler) -> PtaxProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return PtaxProvider(client=client, base_url=_BASE)


def test_usd_usa_endpoint_dolar_e_formato_de_data_americano():
    capturado = {}

    def handler(request):
        capturado["url"] = str(request.url)
        return httpx.Response(200, text=_VALUE_USD)

    provider = _provider(handler)
    cotacoes = provider.buscar_cotacoes(Moeda.USD, date(2026, 6, 5), date(2026, 6, 5))

    assert provider.fonte is Fonte.PTAX
    assert "CotacaoDolarPeriodo" in capturado["url"]
    assert "06-05-2026" in capturado["url"]  # MM-DD-YYYY
    assert cotacoes[0].taxa_compra == Decimal("5.12380")


def test_eur_usa_endpoint_moeda_com_simbolo():
    capturado = {}

    def handler(request):
        capturado["url"] = str(request.url)
        return httpx.Response(200, text=_VALUE_EUR)

    cotacoes = _provider(handler).buscar_cotacoes(
        Moeda.EUR, date(2026, 6, 5), date(2026, 6, 5)
    )
    assert "CotacaoMoedaPeriodo" in capturado["url"]
    assert "EUR" in capturado["url"]
    assert cotacoes[0].taxa_venda == Decimal("5.91000")


def test_fim_de_semana_value_vazio_retorna_lista_vazia():
    def handler(request):
        return httpx.Response(200, json={"value": []})

    assert (
        _provider(handler).buscar_cotacoes(Moeda.USD, date(2026, 6, 6), date(2026, 6, 6))
        == []
    )


def test_value_escalar_levanta_resposta_invalida():
    def handler(request):
        return httpx.Response(200, json={"value": 5})

    with pytest.raises(RespostaInvalida):
        _provider(handler).buscar_cotacoes(Moeda.USD, date(2026, 6, 5), date(2026, 6, 5))


def test_payload_nao_objeto_levanta_resposta_invalida():
    def handler(request):
        return httpx.Response(200, json=[1, 2, 3])

    with pytest.raises(RespostaInvalida):
        _provider(handler).buscar_cotacoes(Moeda.USD, date(2026, 6, 5), date(2026, 6, 5))
