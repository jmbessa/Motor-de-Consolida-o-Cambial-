"""Regra de alertas de materialidade (requisito 6.11).

Uma posição gera alerta quando a divergência entre PTAX e Frankfurter excede
um limite — percentual OU absoluto (em BRL). Os dois gatilhos existem porque
materialidade depende do tamanho da posição: só percentual penaliza mal
posições grandes com pequena divergência relativa; só absoluto penaliza mal
posições pequenas com grande divergência relativa. Limites são
configuráveis; a comparação usa ">" estrito ("acima de") em precisão plena.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, TypeAdapter

from motor_cambial.domain.decimal_utils import DecimalPositivo, DecimalSeguro

_valida_decimal_seguro = TypeAdapter(DecimalSeguro).validate_python


class ConfiguracaoAlerta(BaseModel):
    """Limites configuráveis de materialidade (requisito 6.11)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    limite_percentual: DecimalPositivo = Decimal("1.5")
    limite_absoluto_brl: DecimalPositivo = Decimal("10000")


class MotivoAlerta(StrEnum):
    """Qual gatilho de materialidade disparou o alerta."""

    DIVERGENCIA_PERCENTUAL = "divergencia_percentual"
    DIVERGENCIA_ABSOLUTA = "divergencia_absoluta"


class Alerta(BaseModel):
    """Sinalização de que uma posição excedeu um limite de materialidade."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    exposicao_id: str
    motivo: MotivoAlerta
    valor_observado: DecimalSeguro
    limite: DecimalSeguro


def avaliar_alertas(
    exposicao_id: str,
    diferenca_percentual: Decimal,
    diferenca_absoluta_brl: Decimal,
    config: ConfiguracaoAlerta | None = None,
) -> tuple[Alerta, ...]:
    """Avalia os dois gatilhos de materialidade (percentual OU absoluto).

    Comparação em precisão plena (não no valor já arredondado/exibido) e
    estritamente "acima de" (>): o limite exato não dispara. Uma posição pode
    gerar até 2 alertas (um por motivo).
    """
    diferenca_percentual = _valida_decimal_seguro(diferenca_percentual)
    diferenca_absoluta_brl = _valida_decimal_seguro(diferenca_absoluta_brl)
    config = config or ConfiguracaoAlerta()
    alertas: list[Alerta] = []
    if diferenca_percentual > config.limite_percentual:
        alertas.append(
            Alerta(
                exposicao_id=exposicao_id,
                motivo=MotivoAlerta.DIVERGENCIA_PERCENTUAL,
                valor_observado=diferenca_percentual,
                limite=config.limite_percentual,
            )
        )
    if diferenca_absoluta_brl > config.limite_absoluto_brl:
        alertas.append(
            Alerta(
                exposicao_id=exposicao_id,
                motivo=MotivoAlerta.DIVERGENCIA_ABSOLUTA,
                valor_observado=diferenca_absoluta_brl,
                limite=config.limite_absoluto_brl,
            )
        )
    return tuple(alertas)
