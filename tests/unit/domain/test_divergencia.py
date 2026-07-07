"""Testes da regra de divergência entre PTAX e Frankfurter (por posição)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from motor_cambial.domain.errors import ValorForaDeFaixa
from motor_cambial.domain.rules.divergencia import Divergencia, calcular_divergencia


def test_percentual_tem_base_ptax():
    # PTAX = 1000, Frankfurter = 1020 -> absoluta = 20, percentual = 20/1000*100 = 2.0
    divergencia = calcular_divergencia(
        valor_brl_ptax=Decimal("1000"), valor_brl_frankfurter=Decimal("1020")
    )
    assert divergencia.absoluta_brl == Decimal("20")
    assert divergencia.percentual == Decimal("2.0")


def test_magnitude_e_simetrica_independente_de_quem_e_maior():
    d1 = calcular_divergencia(
        valor_brl_ptax=Decimal("1020"), valor_brl_frankfurter=Decimal("1000")
    )
    d2 = calcular_divergencia(
        valor_brl_ptax=Decimal("1000"), valor_brl_frankfurter=Decimal("1020")
    )
    assert d1.absoluta_brl == d2.absoluta_brl == Decimal("20")


def test_valores_iguais_geram_divergencia_zero():
    divergencia = calcular_divergencia(
        valor_brl_ptax=Decimal("500"), valor_brl_frankfurter=Decimal("500")
    )
    assert divergencia.absoluta_brl == Decimal("0")
    assert divergencia.percentual == Decimal("0")


def test_base_ptax_zero_levanta_erro():
    with pytest.raises(ValorForaDeFaixa):
        calcular_divergencia(
            valor_brl_ptax=Decimal("0"), valor_brl_frankfurter=Decimal("10")
        )


def test_rejeita_float():
    with pytest.raises(ValidationError):
        calcular_divergencia(
            valor_brl_ptax=1000.0, valor_brl_frankfurter=Decimal("1020")
        )


def test_rejeita_nan():
    with pytest.raises(ValidationError):
        calcular_divergencia(
            valor_brl_ptax=Decimal("1000"), valor_brl_frankfurter=Decimal("NaN")
        )


def test_divergencia_e_imutavel():
    divergencia = Divergencia(percentual=Decimal("1"), absoluta_brl=Decimal("1"))
    with pytest.raises(ValidationError):
        divergencia.percentual = Decimal("2")
