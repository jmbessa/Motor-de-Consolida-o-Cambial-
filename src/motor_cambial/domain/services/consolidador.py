"""Serviço puro que agrega um lote de PosicaoAvaliada numa VisaoConsolidada.

Só posições CONSOLIDADA entram nos agregados (totais por moeda, posição
líquida por natureza, top 3 divergências). PARCIAL/FALHA não têm as duas
conversões comparáveis; ficam em ``posicoes_nao_avaliadas`` com o motivo,
para não contaminar os totais com dado incompleto. Ordem dos grupos segue a
primeira aparição no lote (determinístico → base da idempotência da Fatia 6).

Os totais agregados (total_brl_ptax/total_brl_frankfurter/total_brl) são
quantizados para 2 casas (``quantizar_brl``, ROUND_HALF_UP) como defesa em
profundidade na borda de agregação: mesmo que uma parcela individual chegue
com escala irregular, o total sai com escala limpa e estável, o que protege
a idempotência da Fatia 6 (``Decimal("8000.0") == Decimal("8000.00")`` mas
serializam diferente).
"""

from __future__ import annotations

from decimal import Decimal

from motor_cambial.domain.decimal_utils import quantizar_brl
from motor_cambial.domain.enums import Moeda, TipoExposicao
from motor_cambial.domain.resultado import PosicaoAvaliada, StatusPosicao
from motor_cambial.domain.visao_consolidada import (
    PosicaoNaoAvaliada,
    TopDivergencia,
    TotalMoeda,
    TotalNatureza,
    VisaoConsolidada,
)


def consolidar(posicoes: list[PosicaoAvaliada]) -> VisaoConsolidada:
    """Agrega o lote em totais por moeda, posição líquida e top 3 divergências."""
    # posicoes pode ser um iterável de uso único (generator, filter, map);
    # materializar aqui evita esgotá-lo na primeira das duas comprehensions
    # abaixo, o que esvaziaria silenciosamente a segunda.
    posicoes = list(posicoes)
    consolidadas = [
        p for p in posicoes if p.status is StatusPosicao.CONSOLIDADA
    ]
    nao_avaliadas = [
        p for p in posicoes if p.status is not StatusPosicao.CONSOLIDADA
    ]

    return VisaoConsolidada(
        totais_por_moeda=_totais_por_moeda(consolidadas),
        posicao_liquida_por_natureza=_totais_por_natureza(consolidadas),
        top_divergencias=_top_divergencias(consolidadas),
        posicoes_nao_avaliadas=_mapear_nao_avaliadas(nao_avaliadas),
    )


def _totais_por_moeda(
    consolidadas: list[PosicaoAvaliada],
) -> tuple[TotalMoeda, ...]:
    grupos: dict[Moeda, list[PosicaoAvaliada]] = {}
    for p in consolidadas:
        grupos.setdefault(p.exposicao.moeda, []).append(p)
    return tuple(
        TotalMoeda(
            moeda=moeda,
            total_brl_ptax=quantizar_brl(
                sum((p.conversao_ptax.valor_brl for p in grupo), Decimal(0))
            ),
            total_brl_frankfurter=quantizar_brl(
                sum((p.conversao_frankfurter.valor_brl for p in grupo), Decimal(0))
            ),
            quantidade_posicoes=len(grupo),
        )
        for moeda, grupo in grupos.items()
    )


def _totais_por_natureza(
    consolidadas: list[PosicaoAvaliada],
) -> tuple[TotalNatureza, ...]:
    grupos: dict[TipoExposicao, list[PosicaoAvaliada]] = {}
    for p in consolidadas:
        grupos.setdefault(p.exposicao.tipo, []).append(p)
    return tuple(
        TotalNatureza(
            tipo=tipo,
            total_brl=quantizar_brl(
                sum((p.conversao_ptax.valor_brl for p in grupo), Decimal(0))
            ),
            quantidade_posicoes=len(grupo),
        )
        for tipo, grupo in grupos.items()
    )


def _top_divergencias(
    consolidadas: list[PosicaoAvaliada],
) -> tuple[TopDivergencia, ...]:
    ordenadas = sorted(
        consolidadas,
        key=lambda p: p.divergencia.absoluta_brl,
        reverse=True,
    )
    return tuple(
        TopDivergencia(
            exposicao_id=p.exposicao.id,
            divergencia_absoluta_brl=p.divergencia.absoluta_brl,
            divergencia_percentual=p.divergencia.percentual,
        )
        for p in ordenadas[:3]
    )


def _mapear_nao_avaliadas(
    nao_avaliadas: list[PosicaoAvaliada],
) -> tuple[PosicaoNaoAvaliada, ...]:
    return tuple(
        PosicaoNaoAvaliada(
            exposicao_id=p.exposicao.id,
            status=p.status,
            erro_ptax=p.erro_ptax,
            erro_frankfurter=p.erro_frankfurter,
        )
        for p in nao_avaliadas
    )
