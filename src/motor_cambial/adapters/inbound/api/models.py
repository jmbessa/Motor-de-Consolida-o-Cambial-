"""Modelos da borda HTTP (request/response) da API."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from motor_cambial.domain.decimal_utils import DecimalPositivo
from motor_cambial.domain.models import Exposicao


class ConsolidarRequest(BaseModel):
    """Corpo do POST /consolidacoes: exposições + overrides opcionais de config."""

    model_config = ConfigDict(extra="forbid")

    exposicoes: list[Exposicao] = Field(min_length=1)
    data_referencia: date | None = None
    modo_live: bool | None = None
    limite_percentual: DecimalPositivo | None = None
    limite_absoluto: DecimalPositivo | None = None
    janela_dias: int | None = Field(default=None, ge=0, le=3650)
