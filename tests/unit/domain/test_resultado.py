"""Testes de Conversao e PosicaoAvaliada (rastreabilidade + status por posição)."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from motor_cambial.domain.enums import Fonte, Moeda, TipoExposicao, TipoTaxa
from motor_cambial.domain.models import Exposicao
from motor_cambial.domain.resultado import Conversao, PosicaoAvaliada, StatusPosicao
from motor_cambial.domain.rules.alertas import Alerta, MotivoAlerta
from motor_cambial.domain.rules.divergencia import Divergencia


def _exposicao(**overrides):
    dados = dict(
        id="1",
        tipo=TipoExposicao.PAYABLE,
        moeda=Moeda.USD,
        valor="1000",
        vencimento=date(2026, 6, 5),
    )
    dados.update(overrides)
    return Exposicao(**dados)


def _conversao(fonte=Fonte.PTAX, **overrides):
    dados = dict(
        fonte=fonte,
        moeda=Moeda.USD,
        valor_origem=Decimal("1000"),
        data_solicitada=date(2026, 6, 5),
        data_efetiva=date(2026, 6, 5),
        houve_fallback=False,
        defasagem_dias=0,
        tipo_taxa=TipoTaxa.VENDA,
        taxa_aplicada=Decimal("5.05"),
        valor_brl=Decimal("5050.00"),
    )
    dados.update(overrides)
    return Conversao(**dados)


def test_conversao_valida():
    conversao = _conversao()
    assert conversao.fonte is Fonte.PTAX
    assert conversao.valor_brl == Decimal("5050.00")


def test_conversao_e_imutavel():
    conversao = _conversao()
    with pytest.raises(ValidationError):
        conversao.valor_brl = Decimal("1")


def test_conversao_rejeita_fallback_true_com_defasagem_zero():
    with pytest.raises(ValidationError):
        _conversao(houve_fallback=True, defasagem_dias=0)


def test_conversao_rejeita_fallback_false_com_defasagem_positiva():
    with pytest.raises(ValidationError):
        _conversao(houve_fallback=False, defasagem_dias=3)


def test_conversao_com_fallback_coerente():
    conversao = _conversao(
        houve_fallback=True, defasagem_dias=2, data_efetiva=date(2026, 6, 3)
    )
    assert conversao.houve_fallback is True
    assert conversao.defasagem_dias == 2


def test_conversao_rejeita_taxa_zero():
    with pytest.raises(ValidationError):
        _conversao(taxa_aplicada=Decimal("0"))


def test_conversao_rejeita_valor_brl_float():
    with pytest.raises(ValidationError):
        _conversao(valor_brl=5050.0)


def test_conversao_rejeita_campo_extra():
    with pytest.raises(ValidationError):
        _conversao(campo_indevido="x")


def test_posicao_consolidada_exige_as_duas_conversoes():
    posicao = PosicaoAvaliada(
        exposicao=_exposicao(),
        status=StatusPosicao.CONSOLIDADA,
        conversao_ptax=_conversao(fonte=Fonte.PTAX),
        conversao_frankfurter=_conversao(
            fonte=Fonte.FRANKFURTER, tipo_taxa=TipoTaxa.REFERENCIA
        ),
        divergencia=Divergencia(percentual=Decimal("0"), absoluta_brl=Decimal("0")),
        alertas=(),
    )
    assert posicao.status is StatusPosicao.CONSOLIDADA


def test_posicao_consolidada_rejeita_conversao_faltando():
    with pytest.raises(ValidationError):
        PosicaoAvaliada(
            exposicao=_exposicao(),
            status=StatusPosicao.CONSOLIDADA,
            conversao_ptax=_conversao(fonte=Fonte.PTAX),
            erro_frankfurter="fonte fora do ar",
        )


def test_posicao_consolidada_exige_divergencia_presente():
    with pytest.raises(ValidationError):
        PosicaoAvaliada(
            exposicao=_exposicao(),
            status=StatusPosicao.CONSOLIDADA,
            conversao_ptax=_conversao(fonte=Fonte.PTAX),
            conversao_frankfurter=_conversao(
                fonte=Fonte.FRANKFURTER, tipo_taxa=TipoTaxa.REFERENCIA
            ),
            divergencia=None,
        )


def test_posicao_datas_efetivas_divergem_default_false():
    posicao = PosicaoAvaliada(
        exposicao=_exposicao(),
        status=StatusPosicao.CONSOLIDADA,
        conversao_ptax=_conversao(fonte=Fonte.PTAX),
        conversao_frankfurter=_conversao(
            fonte=Fonte.FRANKFURTER, tipo_taxa=TipoTaxa.REFERENCIA
        ),
        divergencia=Divergencia(percentual=Decimal("0"), absoluta_brl=Decimal("0")),
    )
    assert posicao.datas_efetivas_divergem is False


def test_posicao_aceita_datas_efetivas_divergem_true_quando_consolidada():
    posicao = PosicaoAvaliada(
        exposicao=_exposicao(),
        status=StatusPosicao.CONSOLIDADA,
        conversao_ptax=_conversao(fonte=Fonte.PTAX),
        conversao_frankfurter=_conversao(
            fonte=Fonte.FRANKFURTER, tipo_taxa=TipoTaxa.REFERENCIA
        ),
        divergencia=Divergencia(percentual=Decimal("0"), absoluta_brl=Decimal("0")),
        datas_efetivas_divergem=True,
    )
    assert posicao.datas_efetivas_divergem is True


def test_posicao_rejeita_datas_efetivas_divergem_true_fora_de_consolidada():
    with pytest.raises(ValidationError):
        PosicaoAvaliada(
            exposicao=_exposicao(),
            status=StatusPosicao.FALHA,
            erro_ptax="fonte fora do ar",
            erro_frankfurter="moeda não suportada",
            datas_efetivas_divergem=True,
        )


def test_posicao_parcial_exige_erro_da_fonte_faltando():
    posicao = PosicaoAvaliada(
        exposicao=_exposicao(),
        status=StatusPosicao.PARCIAL,
        conversao_ptax=_conversao(fonte=Fonte.PTAX),
        erro_frankfurter="moeda não suportada",
    )
    assert posicao.status is StatusPosicao.PARCIAL
    assert posicao.conversao_frankfurter is None


def test_posicao_parcial_rejeita_erro_e_conversao_juntos_na_mesma_fonte():
    with pytest.raises(ValidationError):
        PosicaoAvaliada(
            exposicao=_exposicao(),
            status=StatusPosicao.PARCIAL,
            conversao_ptax=_conversao(fonte=Fonte.PTAX),
            erro_ptax="não deveria estar aqui",
            erro_frankfurter="moeda não suportada",
        )


def test_posicao_falha_exige_os_dois_erros():
    posicao = PosicaoAvaliada(
        exposicao=_exposicao(),
        status=StatusPosicao.FALHA,
        erro_ptax="fonte fora do ar",
        erro_frankfurter="moeda não suportada",
    )
    assert posicao.status is StatusPosicao.FALHA
    assert posicao.conversao_ptax is None
    assert posicao.conversao_frankfurter is None


def test_posicao_rejeita_divergencia_fora_de_consolidada():
    with pytest.raises(ValidationError):
        PosicaoAvaliada(
            exposicao=_exposicao(),
            status=StatusPosicao.PARCIAL,
            conversao_ptax=_conversao(fonte=Fonte.PTAX),
            erro_frankfurter="moeda não suportada",
            divergencia=Divergencia(percentual=Decimal("0"), absoluta_brl=Decimal("0")),
        )


def test_posicao_rejeita_alertas_fora_de_consolidada():
    with pytest.raises(ValidationError):
        PosicaoAvaliada(
            exposicao=_exposicao(),
            status=StatusPosicao.FALHA,
            erro_ptax="fonte fora do ar",
            erro_frankfurter="moeda não suportada",
            alertas=(
                Alerta(
                    exposicao_id="1",
                    motivo=MotivoAlerta.DIVERGENCIA_PERCENTUAL,
                    valor_observado=Decimal("2"),
                    limite=Decimal("1.5"),
                ),
            ),
        )


def test_posicao_rejeita_conversao_ptax_com_fonte_errada():
    with pytest.raises(ValidationError):
        PosicaoAvaliada(
            exposicao=_exposicao(),
            status=StatusPosicao.PARCIAL,
            conversao_ptax=_conversao(fonte=Fonte.FRANKFURTER),
            erro_frankfurter="moeda não suportada",
        )


def test_posicao_rejeita_conversao_frankfurter_com_fonte_errada():
    with pytest.raises(ValidationError):
        PosicaoAvaliada(
            exposicao=_exposicao(),
            status=StatusPosicao.PARCIAL,
            conversao_ptax=_conversao(fonte=Fonte.PTAX),
            conversao_frankfurter=_conversao(fonte=Fonte.PTAX),
        )


def test_posicao_e_imutavel():
    posicao = PosicaoAvaliada(
        exposicao=_exposicao(),
        status=StatusPosicao.FALHA,
        erro_ptax="fonte fora do ar",
        erro_frankfurter="moeda não suportada",
    )
    with pytest.raises(ValidationError):
        posicao.status = StatusPosicao.CONSOLIDADA
