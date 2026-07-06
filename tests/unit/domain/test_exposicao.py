"""Testes da entidade Exposicao."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from motor_cambial.domain.enums import Moeda, TipoExposicao
from motor_cambial.domain.models import Exposicao


def _exposicao_valida(**overrides):
    dados = dict(
        id="1",
        tipo=TipoExposicao.PAYABLE,
        moeda=Moeda.USD,
        valor="125000",
        vencimento=date(2026, 6, 5),
        descricao="AWS invoice",
    )
    dados.update(overrides)
    return Exposicao(**dados)


def test_cria_exposicao_valida():
    exp = _exposicao_valida()
    assert exp.id == "1"
    assert exp.tipo is TipoExposicao.PAYABLE
    assert exp.moeda is Moeda.USD
    assert exp.valor == Decimal("125000")
    assert exp.vencimento == date(2026, 6, 5)


def test_valor_string_vira_decimal():
    assert _exposicao_valida(valor="98000.50").valor == Decimal("98000.50")


def test_rejeita_valor_zero():
    with pytest.raises(ValidationError):
        _exposicao_valida(valor="0")


def test_rejeita_valor_negativo():
    with pytest.raises(ValidationError):
        _exposicao_valida(valor="-1")


def test_rejeita_valor_float():
    with pytest.raises(ValidationError):
        _exposicao_valida(valor=125000.0)


def test_rejeita_valor_nan():
    with pytest.raises(ValidationError):
        _exposicao_valida(valor="NaN")


def test_rejeita_moeda_desconhecida():
    with pytest.raises(ValidationError):
        _exposicao_valida(moeda="JPY")


def test_rejeita_tipo_desconhecido():
    with pytest.raises(ValidationError):
        _exposicao_valida(tipo="hedge")


def test_rejeita_id_vazio():
    with pytest.raises(ValidationError):
        _exposicao_valida(id="")


def test_rejeita_id_so_espacos():
    with pytest.raises(ValidationError):
        _exposicao_valida(id="   ")


def test_rejeita_campo_extra():
    with pytest.raises(ValidationError):
        _exposicao_valida(natureza="payable")


def test_exposicao_e_imutavel():
    exp = _exposicao_valida()
    with pytest.raises(ValidationError):
        exp.valor = Decimal("1")


def test_aceita_vencimento_passado():
    # Reprocessamento histórico é legítimo: não exigimos data futura.
    exp = _exposicao_valida(vencimento=date(2000, 1, 1))
    assert exp.vencimento == date(2000, 1, 1)


def test_descricao_e_opcional():
    exp = _exposicao_valida(descricao=None) if False else Exposicao(
        id="9",
        tipo=TipoExposicao.RECEIVABLE,
        moeda=Moeda.EUR,
        valor="10",
        vencimento=date(2026, 6, 8),
    )
    assert exp.descricao == ""
