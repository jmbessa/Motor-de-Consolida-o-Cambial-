"""Testes da regra de alertas de materialidade (requisito 6.11)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from motor_cambial.domain.rules.alertas import (
    Alerta,
    ConfiguracaoAlerta,
    MotivoAlerta,
    avaliar_alertas,
)


def test_configuracao_alerta_tem_defaults_do_enunciado():
    config = ConfiguracaoAlerta()
    assert config.limite_percentual == Decimal("1.5")
    assert config.limite_absoluto_brl == Decimal("10000")


def test_somente_percentual_dispara():
    alertas = avaliar_alertas(
        exposicao_id="1",
        diferenca_percentual=Decimal("2.0"),
        diferenca_absoluta_brl=Decimal("100"),
    )
    assert len(alertas) == 1
    assert alertas[0].motivo is MotivoAlerta.DIVERGENCIA_PERCENTUAL
    assert alertas[0].valor_observado == Decimal("2.0")
    assert alertas[0].limite == Decimal("1.5")


def test_somente_absoluto_dispara():
    alertas = avaliar_alertas(
        exposicao_id="1",
        diferenca_percentual=Decimal("0.1"),
        diferenca_absoluta_brl=Decimal("15000"),
    )
    assert len(alertas) == 1
    assert alertas[0].motivo is MotivoAlerta.DIVERGENCIA_ABSOLUTA
    assert alertas[0].valor_observado == Decimal("15000")


def test_ambos_disparam_geram_dois_alertas():
    alertas = avaliar_alertas(
        exposicao_id="1",
        diferenca_percentual=Decimal("5"),
        diferenca_absoluta_brl=Decimal("50000"),
    )
    motivos = {a.motivo for a in alertas}
    assert motivos == {MotivoAlerta.DIVERGENCIA_PERCENTUAL, MotivoAlerta.DIVERGENCIA_ABSOLUTA}


def test_nenhum_dispara_retorna_tupla_vazia():
    alertas = avaliar_alertas(
        exposicao_id="1",
        diferenca_percentual=Decimal("0.5"),
        diferenca_absoluta_brl=Decimal("100"),
    )
    assert alertas == ()


def test_fronteira_exata_nao_dispara():
    # ">" estrito: o limite exato não é "acima de".
    alertas = avaliar_alertas(
        exposicao_id="1",
        diferenca_percentual=Decimal("1.5"),
        diferenca_absoluta_brl=Decimal("10000"),
    )
    assert alertas == ()


def test_fronteira_ligeiramente_acima_dispara():
    alertas = avaliar_alertas(
        exposicao_id="1",
        diferenca_percentual=Decimal("1.5001"),
        diferenca_absoluta_brl=Decimal("10000.01"),
    )
    assert len(alertas) == 2


def test_config_customizada_e_respeitada():
    config = ConfiguracaoAlerta(
        limite_percentual=Decimal("3"), limite_absoluto_brl=Decimal("5000")
    )
    alertas = avaliar_alertas(
        exposicao_id="1",
        diferenca_percentual=Decimal("2"),  # abaixo do limite customizado de 3
        diferenca_absoluta_brl=Decimal("6000"),  # acima do limite customizado de 5000
        config=config,
    )
    assert len(alertas) == 1
    assert alertas[0].motivo is MotivoAlerta.DIVERGENCIA_ABSOLUTA


def test_alerta_registra_exposicao_id():
    alertas = avaliar_alertas(
        exposicao_id="exp-42",
        diferenca_percentual=Decimal("10"),
        diferenca_absoluta_brl=Decimal("0"),
    )
    assert alertas[0].exposicao_id == "exp-42"


def test_alerta_e_imutavel():
    alerta = Alerta(
        exposicao_id="1",
        motivo=MotivoAlerta.DIVERGENCIA_PERCENTUAL,
        valor_observado=Decimal("2"),
        limite=Decimal("1.5"),
    )
    with pytest.raises(ValidationError):
        alerta.valor_observado = Decimal("999")


def test_rejeita_diferenca_percentual_float():
    with pytest.raises(ValidationError):
        avaliar_alertas(
            exposicao_id="1",
            diferenca_percentual=2.0,  # float, não Decimal
            diferenca_absoluta_brl=Decimal("0"),
        )


def test_rejeita_diferenca_absoluta_float():
    with pytest.raises(ValidationError):
        avaliar_alertas(
            exposicao_id="1",
            diferenca_percentual=Decimal("0"),
            diferenca_absoluta_brl=100.0,  # float, não Decimal
        )


def test_rejeita_diferenca_percentual_nan():
    with pytest.raises(ValidationError):
        avaliar_alertas(
            exposicao_id="1",
            diferenca_percentual=Decimal("NaN"),
            diferenca_absoluta_brl=Decimal("0"),
        )
