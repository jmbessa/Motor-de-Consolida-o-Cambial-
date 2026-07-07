"""Testes do serviço de conversão (domain/services/conversor.py)."""

from datetime import date
from decimal import Decimal

import pytest

from motor_cambial.domain.enums import Fonte, Moeda, TipoExposicao, TipoTaxa
from motor_cambial.domain.errors import SemCotacaoNaJanela, ValorForaDeFaixa
from motor_cambial.domain.models import CotacaoNormalizada, Exposicao
from motor_cambial.domain.services.conversor import converter


def _exposicao(tipo=TipoExposicao.PAYABLE, valor="1000", moeda=Moeda.USD):
    return Exposicao(
        id="1", tipo=tipo, moeda=moeda, valor=valor, vencimento=date(2026, 6, 5)
    )


def _cotacao_ptax(data_referencia, compra="5.00", venda="5.10"):
    return CotacaoNormalizada.de_ptax(
        moeda=Moeda.USD,
        data_referencia=data_referencia,
        taxa_compra=compra,
        taxa_venda=venda,
    )


def _cotacao_frankfurter(data_referencia, taxa="5.05"):
    return CotacaoNormalizada.de_frankfurter(
        moeda=Moeda.USD, data_referencia=data_referencia, taxa=taxa
    )


def test_data_exata_sem_fallback():
    exposicao = _exposicao(tipo=TipoExposicao.PAYABLE)
    cotacoes = [_cotacao_ptax(date(2026, 6, 5))]
    conversao = converter(exposicao, cotacoes, date(2026, 6, 5), janela_dias=7)
    assert conversao.data_efetiva == date(2026, 6, 5)
    assert conversao.houve_fallback is False
    assert conversao.defasagem_dias == 0
    assert conversao.fonte is Fonte.PTAX


def test_fim_de_semana_recua_com_fallback():
    # data_referencia cai num fim de semana; só a sexta anterior tem cotação.
    exposicao = _exposicao()
    cotacoes = [_cotacao_ptax(date(2026, 6, 5))]
    conversao = converter(exposicao, cotacoes, date(2026, 6, 7), janela_dias=7)
    assert conversao.data_efetiva == date(2026, 6, 5)
    assert conversao.houve_fallback is True
    assert conversao.defasagem_dias == 2


def test_payable_usa_taxa_de_venda():
    exposicao = _exposicao(tipo=TipoExposicao.PAYABLE, valor="1000")
    cotacoes = [_cotacao_ptax(date(2026, 6, 5), compra="5.00", venda="5.10")]
    conversao = converter(exposicao, cotacoes, date(2026, 6, 5), janela_dias=7)
    assert conversao.tipo_taxa is TipoTaxa.VENDA
    assert conversao.taxa_aplicada == Decimal("5.10")
    assert conversao.valor_brl == Decimal("5100.00")


def test_receivable_usa_taxa_de_compra():
    exposicao = _exposicao(tipo=TipoExposicao.RECEIVABLE, valor="1000")
    cotacoes = [_cotacao_ptax(date(2026, 6, 5), compra="5.00", venda="5.10")]
    conversao = converter(exposicao, cotacoes, date(2026, 6, 5), janela_dias=7)
    assert conversao.tipo_taxa is TipoTaxa.COMPRA
    assert conversao.taxa_aplicada == Decimal("5.00")
    assert conversao.valor_brl == Decimal("5000.00")


def test_intercompany_usa_mid_do_spread_ptax():
    exposicao = _exposicao(tipo=TipoExposicao.INTERCOMPANY, valor="1000")
    cotacoes = [_cotacao_ptax(date(2026, 6, 5), compra="5.00", venda="5.10")]
    conversao = converter(exposicao, cotacoes, date(2026, 6, 5), janela_dias=7)
    assert conversao.tipo_taxa is TipoTaxa.REFERENCIA
    assert conversao.taxa_aplicada == Decimal("5.05")


def test_frankfurter_sem_spread_qualquer_tipo_usa_taxa_unica():
    exposicao = _exposicao(tipo=TipoExposicao.PAYABLE, valor="1000")
    cotacoes = [_cotacao_frankfurter(date(2026, 6, 5), taxa="5.0599")]
    conversao = converter(exposicao, cotacoes, date(2026, 6, 5), janela_dias=7)
    assert conversao.fonte is Fonte.FRANKFURTER
    assert conversao.taxa_aplicada == Decimal("5.0599")


def test_multiplicacao_em_precisao_plena_quantiza_so_o_final():
    # taxa com muitas casas decimais: só o BRL final é arredondado (ROUND_HALF_UP).
    exposicao = _exposicao(tipo=TipoExposicao.PAYABLE, valor="3")
    cotacoes = [_cotacao_ptax(date(2026, 6, 5), compra="1.500000", venda="1.666666")]
    conversao = converter(exposicao, cotacoes, date(2026, 6, 5), janela_dias=7)
    # 3 * 1.666666 = 4.999998 -> quantiza para 5.00 (ROUND_HALF_UP)
    assert conversao.valor_brl == Decimal("5.00")
    assert conversao.taxa_aplicada == Decimal("1.666666")  # taxa preserva a precisão


def test_janela_vazia_levanta_sem_cotacao_na_janela():
    exposicao = _exposicao()
    with pytest.raises(SemCotacaoNaJanela):
        converter(exposicao, [], date(2026, 6, 5), janela_dias=7)


def test_sem_cotacao_dentro_da_janela_levanta_erro():
    exposicao = _exposicao()
    cotacoes = [_cotacao_ptax(date(2026, 5, 1))]  # muito antiga, fora da janela de 7 dias
    with pytest.raises(SemCotacaoNaJanela):
        converter(exposicao, cotacoes, date(2026, 6, 5), janela_dias=7)


def test_ignora_cotacoes_de_moeda_diferente_da_exposicao():
    exposicao = _exposicao(tipo=TipoExposicao.PAYABLE, valor="1000", moeda=Moeda.USD)
    cotacao_errada = CotacaoNormalizada.de_ptax(
        moeda=Moeda.EUR,
        data_referencia=date(2026, 6, 5),
        taxa_compra="6.00",
        taxa_venda="6.10",
    )
    cotacao_certa = _cotacao_ptax(date(2026, 6, 5), compra="5.00", venda="5.10")
    conversao = converter(
        exposicao, [cotacao_errada, cotacao_certa], date(2026, 6, 5), janela_dias=7
    )
    assert conversao.moeda is Moeda.USD
    assert conversao.taxa_aplicada == Decimal("5.10")


def test_apenas_cotacoes_de_moeda_diferente_levanta_sem_cotacao_na_janela():
    exposicao = _exposicao(tipo=TipoExposicao.PAYABLE, valor="1000", moeda=Moeda.USD)
    cotacao_errada = CotacaoNormalizada.de_ptax(
        moeda=Moeda.EUR,
        data_referencia=date(2026, 6, 5),
        taxa_compra="6.00",
        taxa_venda="6.10",
    )
    with pytest.raises(SemCotacaoNaJanela):
        converter(exposicao, [cotacao_errada], date(2026, 6, 5), janela_dias=7)


def test_valor_brl_zero_apos_quantizacao_levanta_valor_fora_de_faixa():
    # exposição minúscula: 0.001 * 1.00 = 0.001 -> quantiza para 0.00 (ROUND_HALF_UP)
    exposicao = _exposicao(tipo=TipoExposicao.PAYABLE, valor="0.001")
    cotacoes = [_cotacao_ptax(date(2026, 6, 5), compra="1.00", venda="1.00")]
    with pytest.raises(ValorForaDeFaixa):
        converter(exposicao, cotacoes, date(2026, 6, 5), janela_dias=7)
