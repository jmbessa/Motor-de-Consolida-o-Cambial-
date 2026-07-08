"""Testes do formatador de relatório de console (função pura)."""

from datetime import date
from decimal import Decimal

from motor_cambial.adapters.inbound.cli.relatorio import formatar_relatorio
from motor_cambial.domain.enums import Fonte, Moeda, TipoExposicao, TipoTaxa
from motor_cambial.domain.models import Exposicao
from motor_cambial.domain.resultado import Conversao, PosicaoAvaliada, StatusPosicao
from motor_cambial.domain.resultado_consolidacao import ResultadoConsolidacao
from motor_cambial.domain.rules.alertas import Alerta, MotivoAlerta
from motor_cambial.domain.rules.divergencia import Divergencia
from motor_cambial.domain.services.consolidador import consolidar


def _conversao(fonte, moeda, valor_brl, tipo_taxa, taxa="5.00",
               data_efetiva=date(2026, 6, 5)):
    houve_fallback = data_efetiva != date(2026, 6, 5)
    return Conversao(
        fonte=fonte, moeda=moeda, valor_origem=Decimal("1000"),
        data_solicitada=date(2026, 6, 5), data_efetiva=data_efetiva,
        houve_fallback=houve_fallback,
        defasagem_dias=(date(2026, 6, 5) - data_efetiva).days,
        tipo_taxa=tipo_taxa,
        taxa_aplicada=Decimal(taxa), valor_brl=Decimal(valor_brl),
    )


def _consolidada(id, moeda, tipo, brl_ptax, brl_frank, abs_brl, pct, com_alerta=False):
    alertas = ()
    if com_alerta:
        alertas = (
            Alerta(
                exposicao_id=id, motivo=MotivoAlerta.DIVERGENCIA_PERCENTUAL,
                valor_observado=Decimal(pct), limite=Decimal("1.5"),
            ),
        )
    return PosicaoAvaliada(
        exposicao=Exposicao(
            id=id, tipo=tipo, moeda=moeda, valor="1000", vencimento=date(2026, 6, 5)
        ),
        status=StatusPosicao.CONSOLIDADA,
        conversao_ptax=_conversao(Fonte.PTAX, moeda, brl_ptax, TipoTaxa.VENDA),
        conversao_frankfurter=_conversao(
            Fonte.FRANKFURTER, moeda, brl_frank, TipoTaxa.REFERENCIA
        ),
        divergencia=Divergencia(percentual=Decimal(pct), absoluta_brl=Decimal(abs_brl)),
        alertas=alertas,
    )


def _parcial(id, moeda, tipo, erro_frankfurter="fonte fora do ar"):
    return PosicaoAvaliada(
        exposicao=Exposicao(
            id=id, tipo=tipo, moeda=moeda, valor="1000", vencimento=date(2026, 6, 5)
        ),
        status=StatusPosicao.PARCIAL,
        conversao_ptax=_conversao(Fonte.PTAX, moeda, "5000.00", TipoTaxa.VENDA),
        erro_frankfurter=erro_frankfurter,
    )


def _resultado(posicoes, data_ref=date(2026, 6, 5), hash_conjunto="a" * 64):
    posicoes = list(posicoes)
    return ResultadoConsolidacao(
        data_referencia=data_ref, hash_conjunto=hash_conjunto,
        posicoes=tuple(posicoes), visao=consolidar(posicoes),
    )


def test_cabecalho_mostra_data_e_contagem_por_status():
    resultado = _resultado([
        _consolidada("1", Moeda.USD, TipoExposicao.PAYABLE,
                     "5000.00", "5050.00", "50.00", "1"),
        _parcial("2", Moeda.EUR, TipoExposicao.RECEIVABLE),
    ])
    texto = formatar_relatorio(resultado)
    assert "2026-06-05" in texto
    assert "1 consolidada(s)" in texto
    assert "1 parcial(is)" in texto
    assert "0 falha(s)" in texto


def test_tabela_de_posicoes_mostra_valores_formatados_em_brl():
    resultado = _resultado([
        _consolidada("1", Moeda.USD, TipoExposicao.PAYABLE,
                     "5100.00", "5050.00", "50.00", "0.98"),
    ])
    texto = formatar_relatorio(resultado)
    assert "R$ 5.100,00" in texto
    assert "R$ 5.050,00" in texto
    assert "0,98%" in texto


def test_alerta_aparece_marcado_no_bloco():
    resultado = _resultado([
        _consolidada("1", Moeda.USD, TipoExposicao.PAYABLE,
                     "5100.00", "4900.00", "200.00", "3.92", com_alerta=True),
    ])
    texto = formatar_relatorio(resultado)
    assert "Alerta: sim" in texto


def test_posicao_parcial_nao_aparece_na_secao_de_posicoes():
    resultado = _resultado([
        _consolidada("1", Moeda.USD, TipoExposicao.PAYABLE,
                     "5100.00", "5050.00", "50.00", "0.98"),
        _parcial("2", Moeda.EUR, TipoExposicao.RECEIVABLE),
    ])
    texto = formatar_relatorio(resultado)
    secao_posicoes = texto.split("--- Posições ---")[1].split(
        "--- Totais por moeda ---"
    )[0]
    linhas = secao_posicoes.splitlines()
    assert not any(linha.startswith("[2]") for linha in linhas)
    assert any(linha.startswith("[1]") for linha in linhas)


def test_bloco_mostra_valor_origem_da_exposicao():
    resultado = _resultado([
        _consolidada("1", Moeda.USD, TipoExposicao.PAYABLE,
                     "5000.00", "5050.00", "50.00", "1"),
    ])
    texto = formatar_relatorio(resultado)
    assert "1.000,00" in texto  # valor_origem = 1000, formato BR


def test_bloco_mostra_taxa_e_tipo_de_taxa_por_fonte():
    resultado = _resultado([
        _consolidada("1", Moeda.USD, TipoExposicao.PAYABLE,
                     "5000.00", "5050.00", "50.00", "1"),
    ])
    texto = formatar_relatorio(resultado)
    assert "taxa 5,00" in texto
    assert "[venda]" in texto        # tipo_taxa do lado PTAX
    assert "[referencia]" in texto   # tipo_taxa do lado Frankfurter


def test_bloco_mostra_data_efetiva_de_cada_fonte():
    resultado = _resultado([
        PosicaoAvaliada(
            exposicao=Exposicao(
                id="1", tipo=TipoExposicao.PAYABLE, moeda=Moeda.USD,
                valor="1000", vencimento=date(2026, 6, 5),
            ),
            status=StatusPosicao.CONSOLIDADA,
            conversao_ptax=_conversao(
                Fonte.PTAX, Moeda.USD, "5000.00", TipoTaxa.VENDA,
                data_efetiva=date(2026, 6, 3),
            ),
            conversao_frankfurter=_conversao(
                Fonte.FRANKFURTER, Moeda.USD, "5050.00", TipoTaxa.REFERENCIA,
                data_efetiva=date(2026, 6, 3),
            ),
            divergencia=Divergencia(
                percentual=Decimal("1"), absoluta_brl=Decimal("50.00")
            ),
        )
    ])
    texto = formatar_relatorio(resultado)
    secao = texto.split("--- Posições ---")[1].split("--- Totais")[0]
    assert "2026-06-03" in secao  # data efetiva do fallback, distinta da referência


def test_totais_por_moeda_aparecem():
    resultado = _resultado([
        _consolidada("1", Moeda.USD, TipoExposicao.PAYABLE,
                     "5000.00", "5000.00", "0", "0"),
    ])
    texto = formatar_relatorio(resultado)
    assert "--- Totais por moeda ---" in texto
    assert "USD:" in texto


def test_posicao_liquida_por_natureza_aparece():
    resultado = _resultado([
        _consolidada("1", Moeda.USD, TipoExposicao.PAYABLE,
                     "5000.00", "5000.00", "0", "0"),
    ])
    texto = formatar_relatorio(resultado)
    assert "--- Posição líquida por natureza ---" in texto
    assert "payable:" in texto


def test_top_divergencias_aparecem_em_ordem():
    resultado = _resultado([
        _consolidada("a", Moeda.USD, TipoExposicao.PAYABLE,
                     "100.00", "150.00", "50.00", "50"),
        _consolidada("b", Moeda.USD, TipoExposicao.PAYABLE,
                     "100.00", "110.00", "10.00", "10"),
    ])
    texto = formatar_relatorio(resultado)
    secao = texto.split("--- Top divergências ---")[1]
    assert secao.index("Exposição a") < secao.index("Exposição b")


def test_nao_avaliadas_aparecem_com_motivo():
    resultado = _resultado([
        _parcial("2", Moeda.EUR, TipoExposicao.RECEIVABLE,
                 erro_frankfurter="moeda não suportada"),
    ])
    texto = formatar_relatorio(resultado)
    assert "--- Posições não avaliadas ---" in texto
    assert "moeda não suportada" in texto


def test_secao_de_nao_avaliadas_e_omitida_quando_vazia():
    resultado = _resultado([
        _consolidada("1", Moeda.USD, TipoExposicao.PAYABLE,
                     "5000.00", "5000.00", "0", "0"),
    ])
    texto = formatar_relatorio(resultado)
    assert "--- Posições não avaliadas ---" not in texto
