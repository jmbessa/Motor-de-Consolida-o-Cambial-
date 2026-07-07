"""Testes do use case reprocessar_por_data (consolida + persiste idempotentemente)."""

from datetime import date, datetime, timezone

import pytest

from motor_cambial.application.use_cases.reprocessar_por_data import (
    reprocessar_por_data,
)
from motor_cambial.domain.enums import Fonte, Moeda, TipoExposicao
from motor_cambial.domain.errors import PersistenciaIndisponivel
from motor_cambial.domain.models import CotacaoNormalizada, Exposicao
from motor_cambial.domain.resultado_consolidacao import (
    RegistroHistorico,
    ResultadoConsolidacao,
)
from motor_cambial.domain.rules.alertas import ConfiguracaoAlerta
from motor_cambial.domain.rules.idempotencia import hash_do_conjunto


class _ProviderFake:
    def __init__(self, fonte, cotacoes=None, erro=None):
        self.fonte = fonte
        self._cotacoes = cotacoes or []
        self._erro = erro

    def buscar_cotacoes(self, moeda, data_inicial, data_final):
        if self._erro is not None:
            raise self._erro
        return self._cotacoes


class _FakeRepo:
    """Repository em memória que espelha a semântica UPSERT + histórico."""

    def __init__(self, salvar_erro=None):
        self.atual: dict[tuple, ResultadoConsolidacao] = {}
        self.historico: dict[tuple, list[RegistroHistorico]] = {}
        self._salvar_erro = salvar_erro

    def salvar(self, resultado):
        if self._salvar_erro is not None:
            raise self._salvar_erro
        chave = (resultado.data_referencia, resultado.hash_conjunto)
        self.atual[chave] = resultado
        entradas = self.historico.setdefault(chave, [])
        entradas.append(
            RegistroHistorico(
                resultado=resultado,
                processado_em=datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc),
                num_processamento=len(entradas) + 1,
            )
        )

    def buscar(self, data_referencia, hash_conjunto):
        return self.atual.get((data_referencia, hash_conjunto))

    def buscar_historico(self, data_referencia, hash_conjunto):
        return tuple(self.historico.get((data_referencia, hash_conjunto), []))


def _exposicao(id="1", moeda=Moeda.USD, tipo=TipoExposicao.PAYABLE):
    return Exposicao(id=id, tipo=tipo, moeda=moeda, valor="1000",
                     vencimento=date(2026, 6, 5))


def _cotacao_ptax(data_ref, compra="5.00", venda="5.10"):
    return CotacaoNormalizada.de_ptax(moeda=Moeda.USD, data_referencia=data_ref,
                                      taxa_compra=compra, taxa_venda=venda)


def _cotacao_frankfurter(data_ref, taxa="5.05"):
    return CotacaoNormalizada.de_frankfurter(moeda=Moeda.USD, data_referencia=data_ref,
                                             taxa=taxa)


def _providers(data_ref):
    return {
        Fonte.PTAX: _ProviderFake(Fonte.PTAX, [_cotacao_ptax(data_ref)]),
        Fonte.FRANKFURTER: _ProviderFake(Fonte.FRANKFURTER, [_cotacao_frankfurter(data_ref)]),
    }


def test_consolida_e_salva_com_hash_correto():
    data_ref = date(2026, 6, 5)
    exposicoes = [_exposicao()]
    repo = _FakeRepo()
    resultado = reprocessar_por_data(exposicoes, _providers(data_ref), data_ref, repo)
    assert isinstance(resultado, ResultadoConsolidacao)
    assert resultado.hash_conjunto == hash_do_conjunto(exposicoes)
    assert resultado.data_referencia == data_ref
    assert len(resultado.posicoes) == 1
    # persistiu: 1 registro atual, 1 no histórico
    chave = (data_ref, resultado.hash_conjunto)
    assert repo.atual[chave] == resultado
    assert len(repo.historico[chave]) == 1


def test_reprocessar_mesma_entrada_e_idempotente():
    data_ref = date(2026, 6, 5)
    exposicoes = [_exposicao()]
    repo = _FakeRepo()
    r1 = reprocessar_por_data(exposicoes, _providers(data_ref), data_ref, repo)
    r2 = reprocessar_por_data(exposicoes, _providers(data_ref), data_ref, repo)
    chave = (data_ref, r1.hash_conjunto)
    assert r1 == r2                       # determinístico
    assert len(repo.atual) == 1            # 1 registro atual (sobrescrito)
    assert len(repo.historico[chave]) == 2  # 2 entradas no histórico (auditoria)


def test_config_diferente_mantem_mesma_chave_natural():
    # config de alerta não entra no hash: mesma data+conjunto -> mesma chave.
    data_ref = date(2026, 6, 5)
    exposicoes = [_exposicao()]
    repo = _FakeRepo()
    reprocessar_por_data(exposicoes, _providers(data_ref), data_ref, repo,
                         config_alerta=ConfiguracaoAlerta())
    from decimal import Decimal
    reprocessar_por_data(exposicoes, _providers(data_ref), data_ref, repo,
                         config_alerta=ConfiguracaoAlerta(limite_percentual=Decimal("0.1")))
    assert len(repo.atual) == 1
    chave = (data_ref, hash_do_conjunto(exposicoes))
    assert len(repo.historico[chave]) == 2


def test_falha_de_persistencia_propaga():
    data_ref = date(2026, 6, 5)
    repo = _FakeRepo(salvar_erro=PersistenciaIndisponivel("db fora do ar"))
    with pytest.raises(PersistenciaIndisponivel):
        reprocessar_por_data([_exposicao()], _providers(data_ref), data_ref, repo)


def test_ordem_das_exposicoes_nao_muda_o_hash_salvo():
    data_ref = date(2026, 6, 5)
    exps_a = [_exposicao(id="1"), _exposicao(id="2", moeda=Moeda.EUR)]
    exps_b = [_exposicao(id="2", moeda=Moeda.EUR), _exposicao(id="1")]
    providers = {
        Fonte.PTAX: _ProviderFake(Fonte.PTAX, [_cotacao_ptax(data_ref)]),
        Fonte.FRANKFURTER: _ProviderFake(Fonte.FRANKFURTER, [_cotacao_frankfurter(data_ref)]),
    }
    r_a = reprocessar_por_data(exps_a, providers, data_ref, _FakeRepo())
    r_b = reprocessar_por_data(exps_b, providers, data_ref, _FakeRepo())
    assert r_a.hash_conjunto == r_b.hash_conjunto
