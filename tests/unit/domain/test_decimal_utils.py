"""Testes dos helpers de Decimal (segurança e política de arredondamento)."""

from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from motor_cambial.domain.decimal_utils import (
    DecimalPositivo,
    DecimalSeguro,
    quantizar_brl,
)

seguro = TypeAdapter(DecimalSeguro)
positivo = TypeAdapter(DecimalPositivo)


# --- DecimalSeguro: aceita entradas exatas ---

def test_decimal_seguro_aceita_string():
    assert seguro.validate_python("1.10") == Decimal("1.10")


def test_decimal_seguro_aceita_int():
    assert seguro.validate_python(125000) == Decimal("125000")


def test_decimal_seguro_aceita_decimal():
    assert seguro.validate_python(Decimal("5.4321")) == Decimal("5.4321")


# --- DecimalSeguro: rejeita entradas perigosas ---

def test_decimal_seguro_rejeita_float():
    # float carrega imprecisão binária: deve ser barrado explicitamente.
    with pytest.raises(ValidationError):
        seguro.validate_python(0.1)


def test_decimal_seguro_rejeita_nan():
    with pytest.raises(ValidationError):
        seguro.validate_python("NaN")


def test_decimal_seguro_rejeita_infinito():
    with pytest.raises(ValidationError):
        seguro.validate_python("Infinity")


def test_decimal_seguro_rejeita_texto_invalido():
    with pytest.raises(ValidationError):
        seguro.validate_python("abc")


def test_decimal_seguro_rejeita_underscore():
    # "1_000" é Decimal válido no Python, mas mascara erro de parse de fonte externa.
    with pytest.raises(ValidationError):
        seguro.validate_python("1_000")


def test_decimal_seguro_preserva_precisao_da_origem():
    # Não quantiza: guarda a precisão como veio (importante para taxas).
    assert seguro.validate_python("5.43210").as_tuple().exponent == -5


# --- DecimalPositivo ---

def test_decimal_positivo_aceita_valor_positivo():
    assert positivo.validate_python("0.01") == Decimal("0.01")


def test_decimal_positivo_rejeita_zero():
    with pytest.raises(ValidationError):
        positivo.validate_python("0")


def test_decimal_positivo_rejeita_negativo():
    with pytest.raises(ValidationError):
        positivo.validate_python("-1")


def test_decimal_positivo_tambem_rejeita_float():
    with pytest.raises(ValidationError):
        positivo.validate_python(1.5)


# --- quantizar_brl: política de arredondamento ---

def test_quantizar_brl_gera_duas_casas():
    assert quantizar_brl(Decimal("5")).as_tuple().exponent == -2
    assert quantizar_brl(Decimal("5")) == Decimal("5.00")


def test_quantizar_brl_usa_half_up_e_nao_bankers():
    # HALF_UP: 0.125 -> 0.13 ; banker's (HALF_EVEN) daria 0.12.
    assert quantizar_brl(Decimal("0.125")) == Decimal("0.13")
    # HALF_UP: 0.135 -> 0.14 ; banker's daria 0.14 também, então usamos o caso acima
    # como distintivo. Este confirma arredondamento para cima do meio.
    assert quantizar_brl(Decimal("2.005")) == Decimal("2.01")


def test_quantizar_brl_nao_arredonda_quando_ja_cabe():
    assert quantizar_brl(Decimal("10.10")) == Decimal("10.10")
