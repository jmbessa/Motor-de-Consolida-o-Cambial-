"""Resultado persistível de uma consolidação (payload + trilha de auditoria).

``ResultadoConsolidacao`` é o bundle completo de um run — as posições
detalhadas e a visão agregada — tudo que o relatório precisa. Serializa de
forma lossless (Decimal preservado como string). ``RegistroHistorico``
envolve um resultado com o momento do processamento e o número da execução,
para a trilha append-only de auditoria.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from motor_cambial.domain.resultado import PosicaoAvaliada
from motor_cambial.domain.visao_consolidada import VisaoConsolidada


class ResultadoConsolidacao(BaseModel):
    """Bundle de um run: posições avaliadas + visão consolidada, por data e hash."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data_referencia: date
    hash_conjunto: str
    posicoes: tuple[PosicaoAvaliada, ...]
    visao: VisaoConsolidada


class RegistroHistorico(BaseModel):
    """Uma entrada da trilha append-only: um resultado, quando e em que execução."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    resultado: ResultadoConsolidacao
    processado_em: datetime
    num_processamento: int = Field(ge=1)

    @model_validator(mode="after")
    def _valida_tz_aware(self) -> "RegistroHistorico":
        if self.processado_em.tzinfo is None:
            raise ValueError("processado_em deve ser timezone-aware (não naive)")
        return self
