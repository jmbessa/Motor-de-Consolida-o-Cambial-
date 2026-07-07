"""Testes do value object CotacaoNormalizada (contrato uniforme das fontes)."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from motor_cambial.domain.enums import Fonte, Moeda, TipoTaxa
from motor_cambial.domain.models import CotacaoNormalizada

BRT = timezone(timedelta(hours=-3))
UMA_DATA = date(2026, 6, 5)


def _ptax(compra="5.10", venda="5.20", **kw):
    return CotacaoNormalizada.de_ptax(
        moeda=Moeda.USD,
        data_referencia=UMA_DATA,
        taxa_compra=compra,
        taxa_venda=venda,
        timestamp=datetime(2026, 6, 5, 13, 0, tzinfo=BRT),
        **kw,
    )


def _frankfurter(mid="5.15", **kw):
    return CotacaoNormalizada.de_frankfurter(
        moeda=Moeda.USD, data_referencia=UMA_DATA, taxa=mid, **kw
    )


def test_ptax_expoe_compra_e_venda_distintas():
    cot = _ptax(compra="5.10", venda="5.20")
    assert cot.fonte is Fonte.PTAX
    assert cot.taxa_compra == Decimal("5.10")
    assert cot.taxa_venda == Decimal("5.20")
    assert cot.possui_spread is True


def test_frankfurter_compra_igual_venda_e_sem_spread():
    cot = _frankfurter(mid="5.15")
    assert cot.fonte is Fonte.FRANKFURTER
    assert cot.taxa_compra == Decimal("5.15")
    assert cot.taxa_venda == Decimal("5.15")
    assert cot.possui_spread is False
    assert cot.timestamp is None


def test_taxa_para_compra_retorna_bid():
    assert _ptax(compra="5.10", venda="5.20").taxa_para(TipoTaxa.COMPRA) == Decimal("5.10")


def test_taxa_para_venda_retorna_ask():
    assert _ptax(compra="5.10", venda="5.20").taxa_para(TipoTaxa.VENDA) == Decimal("5.20")


def test_frankfurter_taxa_para_qualquer_tipo_retorna_mid():
    cot = _frankfurter(mid="5.15")
    assert cot.taxa_para(TipoTaxa.COMPRA) == Decimal("5.15")
    assert cot.taxa_para(TipoTaxa.VENDA) == Decimal("5.15")


def test_taxa_para_aceita_valor_string_do_enum():
    # StrEnum: aceitar o valor ("compra") deve devolver o bid, não cair no else.
    assert _ptax(compra="5.10", venda="5.20").taxa_para("compra") == Decimal("5.10")


def test_taxa_para_rejeita_tipo_invalido():
    cot = _ptax(compra="5.10", venda="5.20")
    with pytest.raises(ValueError):
        cot.taxa_para("lixo")
    with pytest.raises(ValueError):
        cot.taxa_para(None)


def test_possui_spread_rejeita_coercao_lax():
    # Construção direta não pode aceitar 1/"no" como bool: exige bool estrito.
    with pytest.raises(ValidationError):
        CotacaoNormalizada(
            fonte=Fonte.PTAX,
            moeda=Moeda.USD,
            data_referencia=UMA_DATA,
            timestamp=None,
            taxa_compra="5.10",
            taxa_venda="5.20",
            possui_spread=1,
        )


def test_ptax_permite_spread_zero():
    # possui_spread=True significa "a fonte tem mecanismo de spread", não spread>0.
    cot = _ptax(compra="5.10", venda="5.10")
    assert cot.possui_spread is True
    assert cot.taxa_compra == cot.taxa_venda


def test_sem_spread_aceita_taxas_equivalentes_em_notacao_diferente():
    # "5.10" e "5.1" são numericamente iguais; o invariante compra==venda usa
    # igualdade numérica de Decimal (não comparação textual).
    cot = CotacaoNormalizada(
        fonte=Fonte.FRANKFURTER,
        moeda=Moeda.USD,
        data_referencia=UMA_DATA,
        timestamp=None,
        taxa_compra="5.10",
        taxa_venda="5.1",
        possui_spread=False,
    )
    assert cot.taxa_compra == cot.taxa_venda


def test_rejeita_taxa_zero():
    with pytest.raises(ValidationError):
        _ptax(compra="0", venda="5.20")


def test_rejeita_taxa_negativa():
    with pytest.raises(ValidationError):
        _frankfurter(mid="-1")


def test_rejeita_taxa_nan():
    with pytest.raises(ValidationError):
        _frankfurter(mid="NaN")


def test_rejeita_taxa_float():
    with pytest.raises(ValidationError):
        _frankfurter(mid=5.15)


def test_rejeita_venda_menor_que_compra_com_spread():
    with pytest.raises(ValidationError):
        _ptax(compra="5.30", venda="5.20")


def test_incoerencia_sem_spread_com_taxas_diferentes_falha():
    # Construção direta violando o invariante possui_spread=False => compra==venda.
    with pytest.raises(ValidationError):
        CotacaoNormalizada(
            fonte=Fonte.FRANKFURTER,
            moeda=Moeda.USD,
            data_referencia=UMA_DATA,
            timestamp=None,
            taxa_compra="5.10",
            taxa_venda="5.20",
            possui_spread=False,
        )


def test_timestamp_naive_e_rejeitado():
    with pytest.raises(ValidationError):
        CotacaoNormalizada(
            fonte=Fonte.PTAX,
            moeda=Moeda.USD,
            data_referencia=UMA_DATA,
            timestamp=datetime(2026, 6, 5, 13, 0),  # naive: sem tzinfo
            taxa_compra="5.10",
            taxa_venda="5.20",
            possui_spread=True,
        )


def test_taxa_preserva_precisao_da_fonte():
    cot = _ptax(compra="5.43210", venda="5.50000")
    assert cot.taxa_compra.as_tuple().exponent == -5


def test_cotacao_e_imutavel():
    cot = _frankfurter()
    with pytest.raises(ValidationError):
        cot.taxa_compra = Decimal("9")


def test_taxa_para_referencia_retorna_media_ptax():
    cot = _ptax(compra="5.10", venda="5.20")
    assert cot.taxa_para(TipoTaxa.REFERENCIA) == Decimal("5.15")


def test_taxa_para_referencia_retorna_taxa_unica_frankfurter():
    cot = _frankfurter(mid="5.15")
    assert cot.taxa_para(TipoTaxa.REFERENCIA) == Decimal("5.15")


def test_taxa_para_referencia_preserva_precisao():
    # (5.10 + 5.21) / 2 = 5.155 — divisão por 2 sempre termina exatamente.
    cot = _ptax(compra="5.10", venda="5.21")
    assert cot.taxa_para(TipoTaxa.REFERENCIA) == Decimal("5.155")


def test_taxa_para_aceita_valor_string_referencia():
    cot = _ptax(compra="5.10", venda="5.20")
    assert cot.taxa_para("referencia") == Decimal("5.15")
