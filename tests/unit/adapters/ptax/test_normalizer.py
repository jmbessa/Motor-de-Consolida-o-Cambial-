"""Testes do normalizer PTAX (payloads reais capturados)."""

import json
from datetime import date
from decimal import Decimal

import pytest

from motor_cambial.adapters.outbound.ptax.normalizer import normalizar_ptax
from motor_cambial.domain.enums import Fonte, Moeda
from motor_cambial.domain.errors import RespostaInvalida

# USD (CotacaoDolarPeriodo): sem tipoBoletim, já é fechamento.
_VALUE_USD = json.loads(
    '[{"cotacaoCompra":5.12380,"cotacaoVenda":5.12440,'
    '"dataHoraCotacao":"2026-06-05 13:03:38.306"},'
    '{"cotacaoCompra":5.16890,"cotacaoVenda":5.16950,'
    '"dataHoraCotacao":"2026-06-08 13:03:28.848"}]',
    parse_float=Decimal,
)

# EUR (CotacaoMoedaPeriodo): vários boletins; só o Fechamento vale.
_VALUE_EUR = json.loads(
    '[{"cotacaoCompra":5.91540,"cotacaoVenda":5.91760,'
    '"dataHoraCotacao":"2026-06-05 10:08:26.528","tipoBoletim":"Abertura"},'
    '{"cotacaoCompra":5.93370,"cotacaoVenda":5.93490,'
    '"dataHoraCotacao":"2026-06-05 13:03:38.302","tipoBoletim":"Intermediário"},'
    '{"cotacaoCompra":5.90880,"cotacaoVenda":5.91000,'
    '"dataHoraCotacao":"2026-06-05 13:03:38.306","tipoBoletim":"Fechamento"}]',
    parse_float=Decimal,
)


def test_usd_normaliza_com_spread():
    cotacoes = normalizar_ptax(_VALUE_USD, Moeda.USD)
    assert len(cotacoes) == 2
    c = cotacoes[0]
    assert c.fonte is Fonte.PTAX
    assert c.data_referencia == date(2026, 6, 5)
    assert c.taxa_compra == Decimal("5.12380")
    assert c.taxa_venda == Decimal("5.12440")
    assert c.possui_spread is True


def test_timestamp_e_tz_aware_brasilia():
    c = normalizar_ptax(_VALUE_USD, Moeda.USD)[0]
    assert c.timestamp is not None
    assert c.timestamp.tzinfo is not None
    assert c.timestamp.utcoffset().total_seconds() == -3 * 3600


def test_eur_filtra_apenas_fechamento():
    cotacoes = normalizar_ptax(_VALUE_EUR, Moeda.EUR)
    assert len(cotacoes) == 1
    assert cotacoes[0].taxa_compra == Decimal("5.90880")  # o fechamento
    assert cotacoes[0].taxa_venda == Decimal("5.91000")


def test_value_vazio_retorna_lista_vazia():
    assert normalizar_ptax([], Moeda.USD) == []


def test_campo_faltando_levanta_resposta_invalida():
    with pytest.raises(RespostaInvalida):
        normalizar_ptax([{"cotacaoCompra": Decimal("5.1")}], Moeda.USD)


def test_ptax_ordena_por_data_com_entrada_fora_de_ordem():
    value = json.loads(
        '[{"cotacaoCompra":5.20,"cotacaoVenda":5.21,"dataHoraCotacao":"2026-06-08 13:00:00.000"},'
        '{"cotacaoCompra":5.10,"cotacaoVenda":5.11,"dataHoraCotacao":"2026-06-05 13:00:00.000"}]',
        parse_float=Decimal,
    )
    cotacoes = normalizar_ptax(value, Moeda.USD)
    assert [c.data_referencia for c in cotacoes] == [date(2026, 6, 5), date(2026, 6, 8)]


def test_spread_invertido_levanta_resposta_invalida():
    value = json.loads(
        '[{"cotacaoCompra":5.20,"cotacaoVenda":5.10,'  # venda < compra: viola coerência
        '"dataHoraCotacao":"2026-06-05 13:00:00.000"}]',
        parse_float=Decimal,
    )
    with pytest.raises(RespostaInvalida):
        normalizar_ptax(value, Moeda.USD)
