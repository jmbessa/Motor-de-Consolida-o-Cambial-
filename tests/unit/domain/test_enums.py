"""Testes dos enums do domínio."""

import pytest

from motor_cambial.domain.enums import Fonte, Moeda, TipoExposicao, TipoTaxa


def test_tipo_exposicao_tem_tres_membros():
    assert {t.value for t in TipoExposicao} == {"payable", "receivable", "intercompany"}


def test_tipo_taxa_compra_venda_e_referencia():
    assert {t.value for t in TipoTaxa} == {"compra", "venda", "referencia"}


def test_fonte_ptax_e_frankfurter():
    assert {f.value for f in Fonte} == {"ptax", "frankfurter"}


def test_moeda_suporta_conjunto_do_enunciado():
    esperadas = {"USD", "EUR", "GBP", "CAD"}
    assert esperadas.issubset({m.value for m in Moeda})


def test_moeda_desconhecida_nao_pertence_ao_enum():
    with pytest.raises(ValueError):
        Moeda("XYZ")


def test_moeda_e_case_sensitive():
    # Códigos ISO são maiúsculos; "usd" deve ser rejeitado, não normalizado.
    with pytest.raises(ValueError):
        Moeda("usd")


def test_brl_nao_e_moeda_de_exposicao():
    # BRL é a moeda-destino implícita da consolidação, não uma moeda de exposição.
    assert "BRL" not in {m.value for m in Moeda}


def test_enums_sao_strenum():
    # StrEnum: o membro compara/serializa como string.
    assert TipoExposicao.PAYABLE == "payable"
    assert Fonte.PTAX == "ptax"
