"""Resultado de uma consolidação por posição (rastreabilidade + status).

``Conversao`` é a trilha de auditoria de uma conversão de uma exposição para
BRL usando UMA fonte: registra fonte, data solicitada, data efetiva (após
fallback), se houve fallback e sua defasagem, o lado da taxa aplicado e a
taxa em si — tudo que a rastreabilidade (requisito do enunciado) exige.

``PosicaoAvaliada`` pareia as conversões de PTAX e Frankfurter para a mesma
exposição, junto com a divergência e os alertas — ou registra por que uma
ou as duas fontes falharam. O ``status`` é derivado da presença das
conversões e mantido coerente por validação (nunca setado "à mão").

Cada fonte aplica seu próprio fallback de data de forma independente: PTAX
pode resolver exatamente na ``data_referencia`` enquanto Frankfurter cai
alguns dias antes (ou vice-versa). Quando isso acontece, a divergência
calculada mistura duas coisas diferentes — diferença metodológica real
entre as fontes e movimento de mercado entre dias distintos. O campo
``datas_efetivas_divergem`` sinaliza explicitamente esse caso para quem
consome o resultado (ex.: relatórios), sem forçar decisão de negócio aqui.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from motor_cambial.domain.decimal_utils import DecimalPositivo
from motor_cambial.domain.enums import Fonte, Moeda, TipoTaxa
from motor_cambial.domain.models import Exposicao
from motor_cambial.domain.rules.alertas import Alerta
from motor_cambial.domain.rules.divergencia import Divergencia


class StatusPosicao(StrEnum):
    """Situação de uma posição após tentar converter nas duas fontes."""

    CONSOLIDADA = "consolidada"
    PARCIAL = "parcial"
    FALHA = "falha"


class Conversao(BaseModel):
    """Trilha de auditoria de uma conversão de exposição para BRL, por fonte."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fonte: Fonte
    moeda: Moeda
    valor_origem: DecimalPositivo
    data_solicitada: date
    data_efetiva: date
    houve_fallback: bool
    defasagem_dias: int = Field(ge=0)
    tipo_taxa: TipoTaxa
    taxa_aplicada: DecimalPositivo
    valor_brl: DecimalPositivo

    @model_validator(mode="after")
    def _valida_coerencia_fallback(self) -> "Conversao":
        if self.houve_fallback != (self.defasagem_dias > 0):
            raise ValueError(
                "houve_fallback deve ser True se e somente se defasagem_dias > 0"
            )
        return self


class PosicaoAvaliada(BaseModel):
    """Resultado consolidado de uma exposição: conversões, divergência e alertas."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    exposicao: Exposicao
    status: StatusPosicao
    conversao_ptax: Conversao | None = None
    conversao_frankfurter: Conversao | None = None
    erro_ptax: str | None = None
    erro_frankfurter: str | None = None
    divergencia: Divergencia | None = None
    alertas: tuple[Alerta, ...] = ()
    datas_efetivas_divergem: bool = False

    @model_validator(mode="after")
    def _valida_coerencia(self) -> "PosicaoAvaliada":
        if self.conversao_ptax is not None and self.conversao_ptax.fonte is not Fonte.PTAX:
            raise ValueError("conversao_ptax deve ter fonte PTAX")
        if (
            self.conversao_frankfurter is not None
            and self.conversao_frankfurter.fonte is not Fonte.FRANKFURTER
        ):
            raise ValueError("conversao_frankfurter deve ter fonte FRANKFURTER")

        tem_ptax = self.conversao_ptax is not None
        tem_frank = self.conversao_frankfurter is not None

        if tem_ptax and self.erro_ptax is not None:
            raise ValueError("conversao_ptax e erro_ptax não podem coexistir")
        if not tem_ptax and self.erro_ptax is None:
            raise ValueError("erro_ptax é obrigatório quando conversao_ptax é None")
        if tem_frank and self.erro_frankfurter is not None:
            raise ValueError(
                "conversao_frankfurter e erro_frankfurter não podem coexistir"
            )
        if not tem_frank and self.erro_frankfurter is None:
            raise ValueError(
                "erro_frankfurter é obrigatório quando conversao_frankfurter é None"
            )

        n_conversoes = int(tem_ptax) + int(tem_frank)
        status_esperado = {
            2: StatusPosicao.CONSOLIDADA,
            1: StatusPosicao.PARCIAL,
            0: StatusPosicao.FALHA,
        }[n_conversoes]
        if self.status is not status_esperado:
            raise ValueError(
                f"status {self.status!r} incoerente com conversões presentes "
                f"(esperado {status_esperado!r})"
            )

        if self.status is not StatusPosicao.CONSOLIDADA and (
            self.divergencia is not None or self.alertas or self.datas_efetivas_divergem
        ):
            raise ValueError(
                "divergencia, alertas e datas_efetivas_divergem só podem existir "
                "quando status é CONSOLIDADA"
            )
        if self.status is StatusPosicao.CONSOLIDADA and self.divergencia is None:
            raise ValueError(
                "divergencia é obrigatória quando status é CONSOLIDADA"
            )
        return self
