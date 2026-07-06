"""Enums do domínio cambial.

Usamos ``StrEnum`` para que os membros serializem como strings legíveis em
JSON/SQLite e para que a validação de pertinência (valor fora do conjunto ->
erro) seja automática.
"""

from enum import StrEnum


class TipoExposicao(StrEnum):
    """Natureza de uma exposição cambial."""

    PAYABLE = "payable"
    RECEIVABLE = "receivable"
    INTERCOMPANY = "intercompany"


class TipoTaxa(StrEnum):
    """Lado da cotação aplicado na conversão (bid/ask)."""

    COMPRA = "compra"
    VENDA = "venda"


class Fonte(StrEnum):
    """Fonte de cotação consumida."""

    PTAX = "ptax"
    FRANKFURTER = "frankfurter"


class Moeda(StrEnum):
    """Conjunto fechado de moedas estrangeiras suportadas.

    Enum fechado torna "moeda não suportada" um erro de validação explícito e
    testável. ``BRL`` não é membro: é a moeda-destino implícita da consolidação.
    Estender o suporte = adicionar um membro aqui.
    """

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"
