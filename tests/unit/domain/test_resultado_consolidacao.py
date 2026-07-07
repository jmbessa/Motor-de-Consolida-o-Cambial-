"""Testes de ResultadoConsolidacao e RegistroHistorico (payload persistível)."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from motor_cambial.domain.enums import Fonte, Moeda, TipoExposicao, TipoTaxa
from motor_cambial.domain.models import Exposicao
from motor_cambial.domain.resultado import Conversao, PosicaoAvaliada, StatusPosicao
from motor_cambial.domain.resultado_consolidacao import (
    RegistroHistorico,
    ResultadoConsolidacao,
)
from motor_cambial.domain.rules.divergencia import Divergencia
from motor_cambial.domain.services.consolidador import consolidar


def _conversao(fonte, moeda, valor_brl, tipo_taxa, taxa="5.00"):
    return Conversao(
        fonte=fonte, moeda=moeda, valor_origem=Decimal("1000"),
        data_solicitada=date(2026, 6, 5), data_efetiva=date(2026, 6, 5),
        houve_fallback=False, defasagem_dias=0, tipo_taxa=tipo_taxa,
        taxa_aplicada=Decimal(taxa), valor_brl=valor_brl,
    )


def _consolidada():
    return PosicaoAvaliada(
        exposicao=Exposicao(id="1", tipo=TipoExposicao.PAYABLE, moeda=Moeda.USD,
                            valor="1000", vencimento=date(2026, 6, 5)),
        status=StatusPosicao.CONSOLIDADA,
        conversao_ptax=_conversao(Fonte.PTAX, Moeda.USD, Decimal("5100.00"), TipoTaxa.VENDA, "5.10"),
        conversao_frankfurter=_conversao(Fonte.FRANKFURTER, Moeda.USD, Decimal("5050.00"), TipoTaxa.REFERENCIA, "5.05"),
        divergencia=Divergencia(percentual=Decimal("0.98"), absoluta_brl=Decimal("50.00")),
    )


def _resultado():
    posicoes = (_consolidada(),)
    visao = consolidar(list(posicoes))
    return ResultadoConsolidacao(
        data_referencia=date(2026, 6, 5),
        hash_conjunto="a" * 64,
        posicoes=posicoes,
        visao=visao,
    )


def test_resultado_valido():
    r = _resultado()
    assert r.data_referencia == date(2026, 6, 5)
    assert len(r.posicoes) == 1
    assert r.visao.totais_por_moeda[0].moeda is Moeda.USD


def test_resultado_e_imutavel():
    r = _resultado()
    with pytest.raises(ValidationError):
        r.hash_conjunto = "b" * 64


def test_roundtrip_json_preserva_decimais_exatos():
    # A serialização do payload deve ser lossless: Decimal volta idêntico (valor e escala).
    r = _resultado()
    reidratado = ResultadoConsolidacao.model_validate_json(r.model_dump_json())
    assert reidratado == r
    conv = reidratado.posicoes[0].conversao_ptax
    assert conv.valor_brl == Decimal("5100.00")
    assert conv.valor_brl.as_tuple().exponent == -2  # escala preservada
    assert reidratado.visao.totais_por_moeda[0].total_brl_ptax == Decimal("5100.00")


def test_roundtrip_via_dict_json_mode():
    # Idioma usado pelo adapter (coluna JSON): model_dump(mode="json") -> model_validate.
    r = _resultado()
    assert ResultadoConsolidacao.model_validate(r.model_dump(mode="json")) == r


def test_registro_historico_valido():
    reg = RegistroHistorico(
        resultado=_resultado(),
        processado_em=datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc),
        num_processamento=1,
    )
    assert reg.num_processamento == 1


def test_registro_historico_rejeita_processado_em_naive():
    with pytest.raises(ValidationError):
        RegistroHistorico(
            resultado=_resultado(),
            processado_em=datetime(2026, 7, 7, 12, 0),  # naive
            num_processamento=1,
        )


def test_registro_historico_rejeita_num_zero():
    with pytest.raises(ValidationError):
        RegistroHistorico(
            resultado=_resultado(),
            processado_em=datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc),
            num_processamento=0,
        )
