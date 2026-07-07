"""Regra de divergência entre as duas fontes de cotação (por posição).

A divergência mede a diferença entre os valores BRL contábeis (booked) de
cada fonte — o valor que a taxa da regra de seleção (payable->PTAX venda,
receivable->PTAX compra, intercompany->PTAX mid) efetivamente calcula para
cada fonte. A base do percentual é o valor PTAX (âncora oficial brasileira).
Isso significa que a divergência inclui o spread (venda/compra vs mid) —
de propósito: essa é a diferença metodológica entre as fontes que o
enunciado pede para destacar, não um artefato a esconder.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, TypeAdapter

from motor_cambial.domain.decimal_utils import DecimalSeguro
from motor_cambial.domain.errors import ValorForaDeFaixa

_valida_decimal_seguro = TypeAdapter(DecimalSeguro).validate_python


class Divergencia(BaseModel):
    """Magnitude da diferença entre os valores BRL de PTAX e Frankfurter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    percentual: DecimalSeguro
    absoluta_brl: DecimalSeguro


def calcular_divergencia(
    valor_brl_ptax: Decimal, valor_brl_frankfurter: Decimal
) -> Divergencia:
    """Calcula a divergência entre os dois valores BRL contábeis.

    Percentual tem como base ``valor_brl_ptax`` (âncora oficial brasileira).
    Ambos os campos são magnitudes (>= 0); a direção (qual fonte é maior) é
    derivável comparando os dois valores originais. Levanta
    ``ValorForaDeFaixa`` se ``valor_brl_ptax`` for zero (divisão por zero) —
    rede de segurança para uma posição degenerada, não um caso de tesouraria real.
    """
    valor_brl_ptax = _valida_decimal_seguro(valor_brl_ptax)
    valor_brl_frankfurter = _valida_decimal_seguro(valor_brl_frankfurter)
    if valor_brl_ptax == 0:
        raise ValorForaDeFaixa(
            "não é possível calcular divergência percentual com valor_brl_ptax=0"
        )
    absoluta = abs(valor_brl_ptax - valor_brl_frankfurter)
    percentual = absoluta / valor_brl_ptax * 100
    return Divergencia(percentual=percentual, absoluta_brl=absoluta)
