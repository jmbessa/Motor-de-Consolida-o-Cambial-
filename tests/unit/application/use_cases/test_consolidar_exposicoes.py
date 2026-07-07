"""Testes do use case consolidar_exposicoes (orquestração dos providers)."""

from datetime import date

import pytest

from motor_cambial.application.use_cases.consolidar_exposicoes import (
    consolidar_exposicoes,
)
from motor_cambial.domain.enums import Fonte, Moeda, TipoExposicao
from motor_cambial.domain.errors import (
    FonteIndisponivel,
    MoedaNaoSuportadaPelaFonte,
    TipoNaoSuportado,
    ValorForaDeFaixa,
)
from motor_cambial.domain.models import CotacaoNormalizada, Exposicao
from motor_cambial.domain.resultado import StatusPosicao
from motor_cambial.domain.rules.alertas import MotivoAlerta


class _ProviderFake:
    """Provider de teste: devolve cotações fixas ou levanta o erro configurado."""

    def __init__(self, fonte, cotacoes=None, erro=None):
        self.fonte = fonte
        self._cotacoes = cotacoes or []
        self._erro = erro
        self.chamadas: list[tuple] = []

    def buscar_cotacoes(self, moeda, data_inicial, data_final):
        self.chamadas.append((moeda, data_inicial, data_final))
        if self._erro is not None:
            raise self._erro
        return self._cotacoes


class _ProviderMultiFake:
    """Provider fake que responde diferente por moeda (simula falha só p/ uma)."""

    def __init__(self, fonte, respostas):
        self.fonte = fonte
        self._respostas = respostas  # dict[Moeda, list[CotacaoNormalizada] | Exception]

    def buscar_cotacoes(self, moeda, data_inicial, data_final):
        resposta = self._respostas[moeda]
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def _exposicao(id="1", tipo=TipoExposicao.PAYABLE, valor="1000", moeda=Moeda.USD):
    return Exposicao(
        id=id, tipo=tipo, moeda=moeda, valor=valor, vencimento=date(2026, 6, 5)
    )


def _cotacao_ptax(data_referencia, compra="5.00", venda="5.10"):
    return CotacaoNormalizada.de_ptax(
        moeda=Moeda.USD,
        data_referencia=data_referencia,
        taxa_compra=compra,
        taxa_venda=venda,
    )


def _cotacao_frankfurter(data_referencia, taxa="5.05", moeda=Moeda.USD):
    return CotacaoNormalizada.de_frankfurter(
        moeda=moeda, data_referencia=data_referencia, taxa=taxa
    )


def test_duas_fontes_ok_gera_posicao_consolidada():
    data_referencia = date(2026, 6, 5)
    providers = {
        Fonte.PTAX: _ProviderFake(Fonte.PTAX, [_cotacao_ptax(data_referencia)]),
        Fonte.FRANKFURTER: _ProviderFake(
            Fonte.FRANKFURTER, [_cotacao_frankfurter(data_referencia)]
        ),
    }
    resultado = consolidar_exposicoes([_exposicao()], providers, data_referencia)
    assert len(resultado) == 1
    posicao = resultado[0]
    assert posicao.status is StatusPosicao.CONSOLIDADA
    assert posicao.conversao_ptax is not None
    assert posicao.conversao_frankfurter is not None
    assert posicao.divergencia is not None


def test_divergencia_abaixo_do_limite_nao_gera_alerta():
    data_referencia = date(2026, 6, 5)
    # PTAX venda 5.10 (valor_brl=5100.00), Frankfurter 5.05 (valor_brl=5050.00):
    # absoluta=50.00, percentual=50/5100*100=0.98% -> abaixo de 1,5% e de BRL 10.000
    providers = {
        Fonte.PTAX: _ProviderFake(Fonte.PTAX, [_cotacao_ptax(data_referencia)]),
        Fonte.FRANKFURTER: _ProviderFake(
            Fonte.FRANKFURTER, [_cotacao_frankfurter(data_referencia)]
        ),
    }
    resultado = consolidar_exposicoes([_exposicao()], providers, data_referencia)
    assert resultado[0].alertas == ()


def test_alerta_percentual_dispara_quando_divergencia_passa_do_limite():
    data_referencia = date(2026, 6, 5)
    # PTAX venda 5.10 (valor_brl=5100.00) vs Frankfurter 4.90 (valor_brl=4900.00):
    # absoluta=200.00, percentual=200/5100*100=3.92% > 1,5% (absoluto 200 < 10.000)
    providers = {
        Fonte.PTAX: _ProviderFake(
            Fonte.PTAX, [_cotacao_ptax(data_referencia, compra="4.80", venda="5.10")]
        ),
        Fonte.FRANKFURTER: _ProviderFake(
            Fonte.FRANKFURTER, [_cotacao_frankfurter(data_referencia, taxa="4.90")]
        ),
    }
    resultado = consolidar_exposicoes([_exposicao(valor="1000")], providers, data_referencia)
    motivos = {a.motivo for a in resultado[0].alertas}
    assert motivos == {MotivoAlerta.DIVERGENCIA_PERCENTUAL}


def test_alerta_absoluto_dispara_quando_diferenca_brl_passa_do_limite():
    data_referencia = date(2026, 6, 5)
    # posição grande: PTAX venda 5.00 (valor_brl=5.000.000,00), Frankfurter 5.06
    # (valor_brl=5.060.000,00) -> absoluta=60.000,00 > 10.000; percentual=1,2% < 1,5%
    providers = {
        Fonte.PTAX: _ProviderFake(
            Fonte.PTAX, [_cotacao_ptax(data_referencia, compra="4.99", venda="5.00")]
        ),
        Fonte.FRANKFURTER: _ProviderFake(
            Fonte.FRANKFURTER, [_cotacao_frankfurter(data_referencia, taxa="5.06")]
        ),
    }
    resultado = consolidar_exposicoes(
        [_exposicao(valor="1000000")], providers, data_referencia
    )
    motivos = {a.motivo for a in resultado[0].alertas}
    assert motivos == {MotivoAlerta.DIVERGENCIA_ABSOLUTA}


def test_uma_fonte_falha_gera_posicao_parcial():
    data_referencia = date(2026, 6, 5)
    providers = {
        Fonte.PTAX: _ProviderFake(Fonte.PTAX, [_cotacao_ptax(data_referencia)]),
        Fonte.FRANKFURTER: _ProviderFake(
            Fonte.FRANKFURTER, erro=MoedaNaoSuportadaPelaFonte("EUR não suportado")
        ),
    }
    resultado = consolidar_exposicoes([_exposicao()], providers, data_referencia)
    posicao = resultado[0]
    assert posicao.status is StatusPosicao.PARCIAL
    assert posicao.conversao_ptax is not None
    assert posicao.conversao_frankfurter is None
    assert posicao.erro_frankfurter is not None
    assert posicao.divergencia is None
    assert posicao.alertas == ()


def test_fonte_fora_do_ar_e_tratada_como_falha_da_fonte():
    data_referencia = date(2026, 6, 5)
    providers = {
        Fonte.PTAX: _ProviderFake(Fonte.PTAX, erro=FonteIndisponivel("timeout")),
        Fonte.FRANKFURTER: _ProviderFake(
            Fonte.FRANKFURTER, [_cotacao_frankfurter(data_referencia)]
        ),
    }
    resultado = consolidar_exposicoes([_exposicao()], providers, data_referencia)
    assert resultado[0].status is StatusPosicao.PARCIAL
    assert resultado[0].erro_ptax is not None


def test_janela_vazia_e_tratada_como_falha_da_fonte():
    data_referencia = date(2026, 6, 5)
    providers = {
        Fonte.PTAX: _ProviderFake(Fonte.PTAX, []),  # sem cotações -> SemCotacaoNaJanela
        Fonte.FRANKFURTER: _ProviderFake(
            Fonte.FRANKFURTER, [_cotacao_frankfurter(data_referencia)]
        ),
    }
    resultado = consolidar_exposicoes([_exposicao()], providers, data_referencia)
    assert resultado[0].status is StatusPosicao.PARCIAL
    assert resultado[0].erro_ptax is not None


def test_as_duas_fontes_falham_gera_posicao_falha():
    data_referencia = date(2026, 6, 5)
    providers = {
        Fonte.PTAX: _ProviderFake(Fonte.PTAX, erro=FonteIndisponivel("timeout")),
        Fonte.FRANKFURTER: _ProviderFake(
            Fonte.FRANKFURTER, erro=MoedaNaoSuportadaPelaFonte("EUR não suportado")
        ),
    }
    resultado = consolidar_exposicoes([_exposicao()], providers, data_referencia)
    posicao = resultado[0]
    assert posicao.status is StatusPosicao.FALHA
    assert posicao.conversao_ptax is None
    assert posicao.conversao_frankfurter is None


def test_lote_resiliente_uma_posicao_falha_as_demais_seguem():
    data_referencia = date(2026, 6, 5)
    exposicoes = [
        _exposicao(id="1", moeda=Moeda.USD),
        _exposicao(id="2", moeda=Moeda.EUR),
    ]
    providers = {
        Fonte.PTAX: _ProviderMultiFake(
            Fonte.PTAX,
            {
                Moeda.USD: [_cotacao_ptax(data_referencia)],
                Moeda.EUR: MoedaNaoSuportadaPelaFonte("EUR não suportado"),
            },
        ),
        Fonte.FRANKFURTER: _ProviderMultiFake(
            Fonte.FRANKFURTER,
            {
                Moeda.USD: [_cotacao_frankfurter(data_referencia)],
                Moeda.EUR: [
                    _cotacao_frankfurter(data_referencia, taxa="6.10", moeda=Moeda.EUR)
                ],
            },
        ),
    }
    resultado = consolidar_exposicoes(exposicoes, providers, data_referencia)
    assert len(resultado) == 2
    assert resultado[0].status is StatusPosicao.CONSOLIDADA
    assert resultado[1].status is StatusPosicao.PARCIAL  # PTAX falhou p/ EUR


def test_valor_fora_de_faixa_e_tratado_como_falha_da_posicao():
    # Simula uma magnitude que não quantiza (ex.: exposição extrema) — tratado
    # como falha daquela posição (motivo registrado), não propaga como bug.
    data_referencia = date(2026, 6, 5)
    providers = {
        Fonte.PTAX: _ProviderFake(
            Fonte.PTAX, erro=ValorForaDeFaixa("magnitude fora de faixa")
        ),
        Fonte.FRANKFURTER: _ProviderFake(
            Fonte.FRANKFURTER, [_cotacao_frankfurter(data_referencia)]
        ),
    }
    resultado = consolidar_exposicoes([_exposicao()], providers, data_referencia)
    assert resultado[0].status is StatusPosicao.PARCIAL
    assert resultado[0].erro_ptax is not None


def test_quantizacao_para_zero_e_tratada_como_falha_da_posicao_end_to_end():
    # Exposição minúscula faz o PTAX quantizar para BRL 0.00 -> ValorForaDeFaixa
    # é levantado de verdade (não injetado) dentro de converter(), e ainda assim
    # é capturado pela tupla operacional -> PARCIAL, não derruba o lote.
    data_referencia = date(2026, 6, 5)
    providers = {
        Fonte.PTAX: _ProviderFake(
            Fonte.PTAX, [_cotacao_ptax(data_referencia, compra="1.00", venda="1.00")]
        ),
        Fonte.FRANKFURTER: _ProviderFake(
            Fonte.FRANKFURTER, [_cotacao_frankfurter(data_referencia)]
        ),
    }
    resultado = consolidar_exposicoes(
        [_exposicao(valor="0.001")], providers, data_referencia
    )
    assert resultado[0].status is StatusPosicao.PARCIAL
    assert resultado[0].erro_ptax is not None
    assert resultado[0].conversao_frankfurter is not None


def test_datas_efetivas_divergem_quando_fontes_caem_em_datas_diferentes():
    # PTAX tem cotação exata na data_referencia; Frankfurter só tem uma cotação
    # de 2 dias antes (cai em fallback) -> datas_efetivas_divergem deve ser True.
    data_referencia = date(2026, 6, 7)
    providers = {
        Fonte.PTAX: _ProviderFake(Fonte.PTAX, [_cotacao_ptax(data_referencia)]),
        Fonte.FRANKFURTER: _ProviderFake(
            Fonte.FRANKFURTER, [_cotacao_frankfurter(date(2026, 6, 5))]
        ),
    }
    resultado = consolidar_exposicoes([_exposicao()], providers, data_referencia)
    assert resultado[0].status is StatusPosicao.CONSOLIDADA
    assert resultado[0].datas_efetivas_divergem is True


def test_datas_efetivas_nao_divergem_quando_ambas_fontes_na_mesma_data():
    data_referencia = date(2026, 6, 5)
    providers = {
        Fonte.PTAX: _ProviderFake(Fonte.PTAX, [_cotacao_ptax(data_referencia)]),
        Fonte.FRANKFURTER: _ProviderFake(
            Fonte.FRANKFURTER, [_cotacao_frankfurter(data_referencia)]
        ),
    }
    resultado = consolidar_exposicoes([_exposicao()], providers, data_referencia)
    assert resultado[0].datas_efetivas_divergem is False


def test_tiponaosuportado_propaga_e_derruba_a_consolidacao():
    # TipoNaoSuportado é sinal de bug do motor (enum novo sem regra atualizada) —
    # não deve ser engolido como falha operacional de fonte.
    data_referencia = date(2026, 6, 5)
    providers = {
        Fonte.PTAX: _ProviderFake(Fonte.PTAX, erro=TipoNaoSuportado("bug simulado")),
        Fonte.FRANKFURTER: _ProviderFake(
            Fonte.FRANKFURTER, [_cotacao_frankfurter(data_referencia)]
        ),
    }
    with pytest.raises(TipoNaoSuportado):
        consolidar_exposicoes([_exposicao()], providers, data_referencia)


def test_janela_passada_ao_provider_e_data_referencia_menos_janela_dias():
    data_referencia = date(2026, 6, 10)
    provider_ptax = _ProviderFake(Fonte.PTAX, [_cotacao_ptax(data_referencia)])
    provider_frank = _ProviderFake(
        Fonte.FRANKFURTER, [_cotacao_frankfurter(data_referencia)]
    )
    providers = {Fonte.PTAX: provider_ptax, Fonte.FRANKFURTER: provider_frank}
    consolidar_exposicoes([_exposicao()], providers, data_referencia, janela_dias=5)
    moeda, ini, fim = provider_ptax.chamadas[0]
    assert ini == date(2026, 6, 5)
    assert fim == data_referencia


def test_saida_preserva_ordem_de_entrada():
    data_referencia = date(2026, 6, 5)
    providers = {
        Fonte.PTAX: _ProviderFake(Fonte.PTAX, [_cotacao_ptax(data_referencia)]),
        Fonte.FRANKFURTER: _ProviderFake(
            Fonte.FRANKFURTER, [_cotacao_frankfurter(data_referencia)]
        ),
    }
    exposicoes = [_exposicao(id="3"), _exposicao(id="1"), _exposicao(id="2")]
    resultado = consolidar_exposicoes(exposicoes, providers, data_referencia)
    assert [p.exposicao.id for p in resultado] == ["3", "1", "2"]
