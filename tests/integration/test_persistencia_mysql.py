"""Integração do adapter MySQL (opt-in: -m integration + MOTOR_TEST_DB_URL)."""

import os
from datetime import date
from decimal import Decimal

import pytest

from motor_cambial.adapters.outbound.persistence.repository import (
    RepositorioResultadoSQL,
)
from motor_cambial.adapters.outbound.persistence.schema import (
    consolidacao,
    consolidacao_historico,
    criar_schema,
)
from motor_cambial.domain.enums import Fonte, Moeda, TipoExposicao, TipoTaxa
from motor_cambial.domain.models import Exposicao
from motor_cambial.domain.resultado import Conversao, PosicaoAvaliada, StatusPosicao
from motor_cambial.domain.resultado_consolidacao import ResultadoConsolidacao
from motor_cambial.domain.rules.divergencia import Divergencia
from motor_cambial.domain.services.consolidador import consolidar

pytestmark = pytest.mark.integration


@pytest.fixture
def engine():
    url = os.environ.get("MOTOR_TEST_DB_URL")
    if not url:
        pytest.skip("MOTOR_TEST_DB_URL não definido (requer MySQL da Fatia 6b)")
    from sqlalchemy import create_engine

    eng = create_engine(url)
    criar_schema(eng)
    with eng.begin() as conn:
        conn.execute(consolidacao_historico.delete())
        conn.execute(consolidacao.delete())
    yield eng
    eng.dispose()


def _resultado(data_ref=date(2026, 6, 5), hash_conjunto="a" * 64, brl_ptax="5100.00"):
    def _conv(fonte, valor_brl, tipo_taxa, taxa):
        return Conversao(
            fonte=fonte, moeda=Moeda.USD, valor_origem=Decimal("1000"),
            data_solicitada=data_ref, data_efetiva=data_ref, houve_fallback=False,
            defasagem_dias=0, tipo_taxa=tipo_taxa, taxa_aplicada=Decimal(taxa),
            valor_brl=Decimal(valor_brl),
        )

    posicao = PosicaoAvaliada(
        exposicao=Exposicao(id="1", tipo=TipoExposicao.PAYABLE, moeda=Moeda.USD,
                            valor="1000", vencimento=data_ref),
        status=StatusPosicao.CONSOLIDADA,
        conversao_ptax=_conv(Fonte.PTAX, brl_ptax, TipoTaxa.VENDA, "5.10"),
        conversao_frankfurter=_conv(Fonte.FRANKFURTER, "5050.00", TipoTaxa.REFERENCIA, "5.05"),
        divergencia=Divergencia(percentual=Decimal("0.98"), absoluta_brl=Decimal("50.00")),
    )
    return ResultadoConsolidacao(
        data_referencia=data_ref, hash_conjunto=hash_conjunto,
        posicoes=(posicao,), visao=consolidar([posicao]),
    )


def test_roundtrip_decimal_exato(engine):
    repo = RepositorioResultadoSQL(engine)
    resultado = _resultado()
    repo.salvar(resultado)
    lido = repo.buscar(resultado.data_referencia, resultado.hash_conjunto)
    assert lido == resultado
    assert lido.posicoes[0].conversao_ptax.valor_brl == Decimal("5100.00")


def test_upsert_mantem_uma_linha_atual_e_incrementa(engine):
    repo = RepositorioResultadoSQL(engine)
    r = _resultado()
    repo.salvar(r)
    repo.salvar(r)
    with engine.connect() as conn:
        from sqlalchemy import func, select

        n_atual = conn.execute(
            select(func.count()).select_from(consolidacao)
        ).scalar_one()
        num_proc = conn.execute(
            select(consolidacao.c.num_processamentos)
        ).scalar_one()
        n_hist = conn.execute(
            select(func.count()).select_from(consolidacao_historico)
        ).scalar_one()
    assert n_atual == 1
    assert num_proc == 2
    assert n_hist == 2


def test_buscar_historico_ordenado(engine):
    repo = RepositorioResultadoSQL(engine)
    r = _resultado()
    repo.salvar(r)
    repo.salvar(r)
    historico = repo.buscar_historico(r.data_referencia, r.hash_conjunto)
    assert [h.num_processamento for h in historico] == [1, 2]
    assert all(h.processado_em.tzinfo is not None for h in historico)


def test_chave_natural_distinta_gera_linha_separada(engine):
    repo = RepositorioResultadoSQL(engine)
    repo.salvar(_resultado(hash_conjunto="a" * 64))
    repo.salvar(_resultado(hash_conjunto="b" * 64))
    with engine.connect() as conn:
        from sqlalchemy import func, select

        n = conn.execute(select(func.count()).select_from(consolidacao)).scalar_one()
    assert n == 2


def test_buscar_inexistente_retorna_none(engine):
    repo = RepositorioResultadoSQL(engine)
    assert repo.buscar(date(2099, 1, 1), "f" * 64) is None
