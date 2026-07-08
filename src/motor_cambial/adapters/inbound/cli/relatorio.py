"""Formata um ResultadoConsolidacao em relatório de console (texto puro).

Função pura — só formata a string a partir do que já foi calculado pelo
domínio/aplicação; não faz I/O, não recalcula nada. Cada seção (bloco por
posição — com valor original, taxa, data efetiva e BRL de cada fonte —, totais
por moeda, posição líquida por natureza, top divergências, não avaliadas) é
omitida se a coleção correspondente estiver vazia — nunca imprime um cabeçalho
de seção sem conteúdo.
"""

from __future__ import annotations

from decimal import Decimal

from motor_cambial.domain.resultado import StatusPosicao
from motor_cambial.domain.resultado_consolidacao import ResultadoConsolidacao


def _fmt_num(valor: Decimal) -> str:
    """Número no formato brasileiro (milhar '.', decimal ',') com 2 casas, sem R$."""
    texto = f"{valor:,.2f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def _fmt_brl(valor: Decimal) -> str:
    return f"R$ {_fmt_num(valor)}"


def _fmt_taxa(valor: Decimal) -> str:
    """Taxa preservando a precisão da fonte, com vírgula decimal (não é BRL)."""
    return f"{valor}".replace(".", ",")


def _fmt_pct(valor: Decimal) -> str:
    return f"{valor:.2f}".replace(".", ",") + "%"


def formatar_relatorio(resultado: ResultadoConsolidacao) -> str:
    """Monta o relatório de console a partir de um ResultadoConsolidacao."""
    linhas: list[str] = []
    posicoes = resultado.posicoes
    consolidadas = [p for p in posicoes if p.status is StatusPosicao.CONSOLIDADA]
    parciais = sum(1 for p in posicoes if p.status is StatusPosicao.PARCIAL)
    falhas = sum(1 for p in posicoes if p.status is StatusPosicao.FALHA)

    linhas.append(
        f"=== Motor de Consolidação Cambial — "
        f"{resultado.data_referencia.isoformat()} ==="
    )
    linhas.append(
        f"Posições ({len(posicoes)}): {len(consolidadas)} consolidada(s), "
        f"{parciais} parcial(is), {falhas} falha(s)"
    )
    linhas.append("")

    if consolidadas:
        linhas.append("--- Posições ---")
        for p in consolidadas:
            exp = p.exposicao
            linhas.append(
                f"[{exp.id}] {exp.tipo.value}  {exp.moeda.value}  "
                f"{_fmt_num(p.conversao_ptax.valor_origem)}"
            )
            for rotulo, conv in (
                ("PTAX", p.conversao_ptax),
                ("Frankfurter", p.conversao_frankfurter),
            ):
                linhas.append(
                    f"    {rotulo:<12}{conv.data_efetiva.isoformat()}  "
                    f"taxa {_fmt_taxa(conv.taxa_aplicada):<9}[{conv.tipo_taxa.value}]"
                    f"  →  {_fmt_brl(conv.valor_brl)}"
                )
            alerta = "sim" if p.alertas else "-"
            linhas.append(
                f"    Divergência  {_fmt_pct(p.divergencia.percentual)}  "
                f"({_fmt_brl(p.divergencia.absoluta_brl)})    Alerta: {alerta}"
            )
            linhas.append("")

    if resultado.visao.totais_por_moeda:
        linhas.append("--- Totais por moeda ---")
        for t in resultado.visao.totais_por_moeda:
            linhas.append(
                f"{t.moeda.value}: PTAX {_fmt_brl(t.total_brl_ptax)}  "
                f"Frankfurter {_fmt_brl(t.total_brl_frankfurter)}  "
                f"({t.quantidade_posicoes} posição(ões))"
            )
        linhas.append("")

    if resultado.visao.posicao_liquida_por_natureza:
        linhas.append("--- Posição líquida por natureza ---")
        for t in resultado.visao.posicao_liquida_por_natureza:
            linhas.append(
                f"{t.tipo.value}: {_fmt_brl(t.total_brl)} "
                f"({t.quantidade_posicoes} posição(ões))"
            )
        linhas.append("")

    if resultado.visao.top_divergencias:
        linhas.append("--- Top divergências ---")
        for i, d in enumerate(resultado.visao.top_divergencias, start=1):
            linhas.append(
                f"{i}. Exposição {d.exposicao_id} — "
                f"{_fmt_brl(d.divergencia_absoluta_brl)} "
                f"({_fmt_pct(d.divergencia_percentual)})"
            )
        linhas.append("")

    if resultado.visao.posicoes_nao_avaliadas:
        linhas.append("--- Posições não avaliadas ---")
        for na in resultado.visao.posicoes_nao_avaliadas:
            motivos = ", ".join(
                m for m in (na.erro_ptax, na.erro_frankfurter) if m is not None
            )
            linhas.append(
                f"- Exposição {na.exposicao_id} ({na.status.value}): {motivos}"
            )
        linhas.append("")

    return "\n".join(linhas).rstrip("\n") + "\n"
