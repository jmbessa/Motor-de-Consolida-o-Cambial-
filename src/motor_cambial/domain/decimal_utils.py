"""Helpers de ``Decimal``: segurança de entrada e política de arredondamento.

Dinheiro nunca é representado por ``float`` (imprecisão binária). Estes helpers
formam a cerca de segurança em torno de todo valor monetário/taxa do domínio:

- ``DecimalSeguro``: rejeita ``float`` e não-finitos (``NaN``/``Infinity``).
- ``DecimalPositivo``: ``DecimalSeguro`` que ainda exige ``> 0``.
- ``quantizar_brl``: arredonda BRL a 2 casas com ``ROUND_HALF_UP`` (convenção
  financeira brasileira — e **não** o ``ROUND_HALF_EVEN`` default do Python).
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Annotated

from pydantic import BeforeValidator, Field

CENTAVOS = Decimal("0.01")
ARREDONDAMENTO = ROUND_HALF_UP


def _valida_decimal_seguro(valor: object) -> Decimal:
    """Converte para ``Decimal`` rejeitando entradas perigosas.

    - ``float``/``bool``: barrados (imprecisão binária silenciosa).
    - ``NaN``/``Infinity``: barrados (são ``Decimal`` válidos, mas envenenam
      cálculos).
    - Aceita ``str``, ``int`` e ``Decimal``.
    """
    if isinstance(valor, bool):
        raise ValueError("valor booleano não é um Decimal monetário válido")
    if isinstance(valor, float):
        raise ValueError(
            "use str ou Decimal em vez de float para preservar a precisão"
        )
    if isinstance(valor, str) and "_" in valor:
        # "1_000" é Decimal válido no Python, mas costuma mascarar erro de parse.
        raise ValueError("string numérica não pode conter '_'")
    try:
        convertido = valor if isinstance(valor, Decimal) else Decimal(valor)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"valor não conversível para Decimal: {valor!r}") from exc
    if not convertido.is_finite():
        raise ValueError("Decimal deve ser finito (NaN/Infinity não permitidos)")
    return convertido


DecimalSeguro = Annotated[Decimal, BeforeValidator(_valida_decimal_seguro)]
DecimalPositivo = Annotated[DecimalSeguro, Field(gt=0)]


def quantizar_brl(valor: Decimal) -> Decimal:
    """Arredonda um valor em BRL para 2 casas com ``ROUND_HALF_UP``."""
    return valor.quantize(CENTAVOS, rounding=ARREDONDAMENTO)
