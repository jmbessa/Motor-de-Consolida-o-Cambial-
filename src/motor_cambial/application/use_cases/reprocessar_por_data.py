"""Use case: processa (ou reprocessa) uma data e persiste idempotentemente.

Calcula a identidade do run (``hash_do_conjunto``), consolida via os use
cases/serviços já existentes (``consolidar_exposicoes`` + ``consolidar``),
monta o ``ResultadoConsolidacao`` e o persiste pelo port
``ResultadoRepository``. Sempre recomputa e salva — a idempotência vem da
chave natural no adapter (UPSERT), não de um short-circuit aqui. O use case
não faz I/O nem carimba tempo: isso é responsabilidade do adapter.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from motor_cambial.application.use_cases.consolidar_exposicoes import (
    consolidar_exposicoes,
)
from motor_cambial.domain.enums import Fonte
from motor_cambial.domain.models import Exposicao
from motor_cambial.domain.resultado_consolidacao import ResultadoConsolidacao
from motor_cambial.domain.rules.alertas import ConfiguracaoAlerta
from motor_cambial.domain.rules.idempotencia import hash_do_conjunto
from motor_cambial.domain.services.consolidador import consolidar
from motor_cambial.ports.cotacao_provider import CotacaoProvider
from motor_cambial.ports.resultado_repository import ResultadoRepository


def reprocessar_por_data(
    exposicoes: Sequence[Exposicao],
    providers: Mapping[Fonte, CotacaoProvider],
    data_referencia: date,
    repository: ResultadoRepository,
    config_alerta: ConfiguracaoAlerta | None = None,
    janela_dias: int = 7,
) -> ResultadoConsolidacao:
    """Consolida a data e persiste o resultado (idempotente por chave natural)."""
    hash_conjunto = hash_do_conjunto(exposicoes)
    posicoes = consolidar_exposicoes(
        exposicoes, providers, data_referencia, config_alerta, janela_dias
    )
    visao = consolidar(posicoes)
    resultado = ResultadoConsolidacao(
        data_referencia=data_referencia,
        hash_conjunto=hash_conjunto,
        posicoes=tuple(posicoes),
        visao=visao,
    )
    repository.salvar(resultado)
    return resultado
