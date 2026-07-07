"""Port de cotação: contrato que os adapters de fonte implementam."""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from motor_cambial.domain.enums import Fonte, Moeda
from motor_cambial.domain.models import CotacaoNormalizada


@runtime_checkable
class CotacaoProvider(Protocol):
    """Busca cotações normalizadas de uma fonte, por janela de datas.

    ``buscar_cotacoes`` retorna as cotações de fechamento de cada dia útil
    disponível em ``[data_inicial, data_final]``, ordenadas por
    ``data_referencia``. Lista vazia se não houver dado (dia sem cotação não é
    erro). Levanta ``MoedaNaoSuportadaPelaFonte``, ``FonteIndisponivel`` ou
    ``RespostaInvalida`` conforme o caso.
    """

    fonte: Fonte

    def buscar_cotacoes(
        self, moeda: Moeda, data_inicial: date, data_final: date
    ) -> list[CotacaoNormalizada]: ...
