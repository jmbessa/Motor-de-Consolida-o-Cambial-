"""Use case: consolida uma lista de exposições em BRL usando as duas fontes.

Para cada exposição, busca a janela de cotações de cada fonte, converte
(``domain.services.conversor.converter``), mede a divergência entre os
valores BRL contábeis e avalia os alertas de materialidade. Erros
operacionais de uma fonte (moeda não suportada, sem cotação na janela,
fonte fora do ar, resposta malformada, valor fora de faixa) não derrubam o
lote — a posição fica PARCIAL/FALHA com o motivo registrado.
``TipoNaoSuportado`` e qualquer erro fora dessa tupla são bugs do motor e
propagam (ver ``_ERROS_OPERACIONAIS``).

Quando as duas fontes convertem, também comparamos a ``data_efetiva`` de
cada uma: cada fonte aplica seu próprio fallback de data de forma
independente, então PTAX e Frankfurter podem acabar resolvendo em datas
diferentes para a mesma posição. Isso é sinalizado em
``PosicaoAvaliada.datas_efetivas_divergem``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, timedelta

from motor_cambial.domain.enums import Fonte
from motor_cambial.domain.errors import (
    FonteIndisponivel,
    MoedaNaoSuportadaPelaFonte,
    RespostaInvalida,
    SemCotacaoNaJanela,
    ValorForaDeFaixa,
)
from motor_cambial.domain.models import Exposicao
from motor_cambial.domain.resultado import Conversao, PosicaoAvaliada, StatusPosicao
from motor_cambial.domain.rules.alertas import ConfiguracaoAlerta, avaliar_alertas
from motor_cambial.domain.rules.divergencia import calcular_divergencia
from motor_cambial.domain.services.conversor import converter
from motor_cambial.ports.cotacao_provider import CotacaoProvider

_ERROS_OPERACIONAIS = (
    MoedaNaoSuportadaPelaFonte,
    SemCotacaoNaJanela,
    FonteIndisponivel,
    RespostaInvalida,
    ValorForaDeFaixa,
)


def _converter_por_fonte(
    exposicao: Exposicao,
    provider: CotacaoProvider,
    data_referencia: date,
    janela_dias: int,
) -> tuple[Conversao | None, str | None]:
    """Busca a janela e converte numa fonte; erro operacional vira motivo."""
    try:
        cotacoes = provider.buscar_cotacoes(
            exposicao.moeda,
            data_referencia - timedelta(days=janela_dias),
            data_referencia,
        )
        conversao = converter(exposicao, cotacoes, data_referencia, janela_dias)
        return conversao, None
    except _ERROS_OPERACIONAIS as exc:
        return None, str(exc)


def _avaliar_posicao(
    exposicao: Exposicao,
    providers: Mapping[Fonte, CotacaoProvider],
    data_referencia: date,
    config_alerta: ConfiguracaoAlerta,
    janela_dias: int,
) -> PosicaoAvaliada:
    conversao_ptax, erro_ptax = _converter_por_fonte(
        exposicao, providers[Fonte.PTAX], data_referencia, janela_dias
    )
    conversao_frankfurter, erro_frankfurter = _converter_por_fonte(
        exposicao, providers[Fonte.FRANKFURTER], data_referencia, janela_dias
    )

    if conversao_ptax is not None and conversao_frankfurter is not None:
        divergencia = calcular_divergencia(
            conversao_ptax.valor_brl, conversao_frankfurter.valor_brl
        )
        alertas = avaliar_alertas(
            exposicao.id,
            divergencia.percentual,
            divergencia.absoluta_brl,
            config_alerta,
        )
        datas_efetivas_divergem = (
            conversao_ptax.data_efetiva != conversao_frankfurter.data_efetiva
        )
        status = StatusPosicao.CONSOLIDADA
    else:
        divergencia = None
        alertas = ()
        datas_efetivas_divergem = False
        n_conversoes = int(conversao_ptax is not None) + int(
            conversao_frankfurter is not None
        )
        status = StatusPosicao.PARCIAL if n_conversoes == 1 else StatusPosicao.FALHA

    return PosicaoAvaliada(
        exposicao=exposicao,
        status=status,
        conversao_ptax=conversao_ptax,
        conversao_frankfurter=conversao_frankfurter,
        erro_ptax=erro_ptax,
        erro_frankfurter=erro_frankfurter,
        divergencia=divergencia,
        alertas=alertas,
        datas_efetivas_divergem=datas_efetivas_divergem,
    )


def consolidar_exposicoes(
    exposicoes: Sequence[Exposicao],
    providers: Mapping[Fonte, CotacaoProvider],
    data_referencia: date,
    config_alerta: ConfiguracaoAlerta | None = None,
    janela_dias: int = 7,
) -> list[PosicaoAvaliada]:
    """Consolida cada exposição em BRL nas duas fontes, na ordem de entrada."""
    config_alerta = config_alerta or ConfiguracaoAlerta()
    return [
        _avaliar_posicao(
            exposicao, providers, data_referencia, config_alerta, janela_dias
        )
        for exposicao in exposicoes
    ]
