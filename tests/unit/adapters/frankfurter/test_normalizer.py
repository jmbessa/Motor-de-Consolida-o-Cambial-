"""Testes do normalizer da Frankfurter (payloads reais capturados)."""

import json
from datetime import date
from decimal import Decimal

import pytest

from motor_cambial.adapters.outbound.frankfurter.normalizer import (
    normalizar_frankfurter,
)
from motor_cambial.domain.enums import Fonte, Moeda
from motor_cambial.domain.errors import MoedaNaoSuportadaPelaFonte, RespostaInvalida

# Payload real do endpoint de intervalo (2026-06-01..2026-06-08, USD->BRL).
_INTERVALO = json.loads(
    '{"amount":1.0,"base":"USD","start_date":"2026-06-01","end_date":"2026-06-08",'
    '"rates":{"2026-06-01":{"BRL":5.0245},"2026-06-05":{"BRL":5.0599},'
    '"2026-06-08":{"BRL":5.1432}}}',
    parse_float=Decimal,
)


def test_normaliza_intervalo_uma_cotacao_por_data():
    cotacoes = normalizar_frankfurter(_INTERVALO, Moeda.USD)
    assert len(cotacoes) == 3
    assert [c.data_referencia for c in cotacoes] == [
        date(2026, 6, 1),
        date(2026, 6, 5),
        date(2026, 6, 8),
    ]  # ordenado por data


def test_ordena_por_data_mesmo_com_entrada_fora_de_ordem():
    # rates com datas fora de ordem: prova que a ordenação é feita pelo normalizer,
    # não herdada da ordem de inserção do payload.
    payload = json.loads(
        '{"rates":{"2026-06-08":{"BRL":5.1432},"2026-06-01":{"BRL":5.0245},'
        '"2026-06-05":{"BRL":5.0599}}}',
        parse_float=Decimal,
    )
    cotacoes = normalizar_frankfurter(payload, Moeda.USD)
    assert [c.data_referencia for c in cotacoes] == [
        date(2026, 6, 1),
        date(2026, 6, 5),
        date(2026, 6, 8),
    ]


def test_cotacao_frankfurter_sem_spread_e_sem_timestamp():
    cotacoes = normalizar_frankfurter(_INTERVALO, Moeda.USD)
    c = next(c for c in cotacoes if c.data_referencia == date(2026, 6, 5))
    assert c.fonte is Fonte.FRANKFURTER
    assert c.taxa_compra == Decimal("5.0599")
    assert c.taxa_venda == Decimal("5.0599")
    assert c.possui_spread is False
    assert c.timestamp is None


def test_moeda_inexistente_levanta_erro():
    payload = json.loads('{"message":"not found"}', parse_float=Decimal)
    with pytest.raises(MoedaNaoSuportadaPelaFonte):
        normalizar_frankfurter(payload, Moeda.USD)


def test_payload_sem_rates_e_sem_message_e_invalido():
    with pytest.raises(RespostaInvalida):
        normalizar_frankfurter({"amount": Decimal("1")}, Moeda.USD)


def test_rate_sem_brl_e_invalido():
    payload = {"rates": {"2026-06-05": {"USD": Decimal("1")}}}
    with pytest.raises(RespostaInvalida):
        normalizar_frankfurter(payload, Moeda.USD)


def test_rates_nao_dict_levanta_resposta_invalida():
    with pytest.raises(RespostaInvalida):
        normalizar_frankfurter({"rates": []}, Moeda.USD)


def test_taxa_zero_ou_negativa_levanta_resposta_invalida():
    payload = {"rates": {"2026-06-05": {"BRL": Decimal("0")}}}
    with pytest.raises(RespostaInvalida):
        normalizar_frankfurter(payload, Moeda.USD)


def test_payload_nao_objeto_levanta_resposta_invalida():
    with pytest.raises(RespostaInvalida):
        normalizar_frankfurter([1, 2, 3], Moeda.USD)
