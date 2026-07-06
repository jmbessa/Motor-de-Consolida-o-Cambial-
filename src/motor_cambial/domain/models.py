"""Modelos do domínio cambial (puros, sem I/O)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StringConstraints,
    model_validator,
)

from motor_cambial.domain.decimal_utils import DecimalPositivo
from motor_cambial.domain.enums import Fonte, Moeda, TipoExposicao, TipoTaxa

IdNaoVazio = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Exposicao(BaseModel):
    """Um compromisso financeiro futuro em moeda estrangeira.

    O ``valor`` é o montante do compromisso e é **sempre positivo**: a natureza
    (entrada ou saída de caixa) é dada por ``tipo``, não pelo sinal. Não exigimos
    ``vencimento`` futuro — reprocessamento histórico é um caso legítimo.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: IdNaoVazio
    tipo: TipoExposicao
    moeda: Moeda
    valor: DecimalPositivo
    vencimento: date
    descricao: str = ""


class CotacaoNormalizada(BaseModel):
    """Cotação de uma moeda contra o BRL, normalizada das duas fontes.

    Contrato uniforme que o conversor consome sem precisar saber a fonte. A PTAX
    tem spread (compra/venda distintas); a Frankfurter é uma taxa de referência
    única, modelada como ``taxa_compra == taxa_venda`` com ``possui_spread=False``
    — preservando a diferença metodológica sem forçar ramos condicionais.

    ``data_referencia`` é a data de negócio da cotação — o eixo de seleção e
    fallback. ``timestamp`` é metadado de auditoria (momento exato do boletim) e é
    **intencionalmente independente** de ``data_referencia``: quando presente, deve
    ser *timezone-aware* para evitar comparações ambíguas, mas não é cruzado com a
    data de referência (fontes podem carimbar horários em fusos distintos).

    ``possui_spread`` indica que a fonte **tem mecanismo de compra/venda** (PTAX),
    não que o spread seja necessariamente maior que zero.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fonte: Fonte
    moeda: Moeda
    data_referencia: date
    timestamp: datetime | None = None
    taxa_compra: DecimalPositivo
    taxa_venda: DecimalPositivo
    possui_spread: StrictBool

    @model_validator(mode="after")
    def _valida_coerencia(self) -> "CotacaoNormalizada":
        if self.timestamp is not None and self.timestamp.tzinfo is None:
            raise ValueError("timestamp deve ser timezone-aware (não naive)")
        if self.possui_spread:
            if self.taxa_venda < self.taxa_compra:
                raise ValueError(
                    "com spread, taxa_venda (ask) deve ser >= taxa_compra (bid)"
                )
        elif self.taxa_compra != self.taxa_venda:
            raise ValueError(
                "sem spread, taxa_compra e taxa_venda devem ser iguais"
            )
        return self

    def taxa_para(self, tipo: TipoTaxa) -> Decimal:
        """Retorna a taxa do lado pedido (COMPRA=bid, VENDA=ask).

        Aceita o membro do enum ou seu valor (ex.: ``"compra"``) e **rejeita**
        qualquer outro input com ``ValueError`` — nunca decide a taxa por um ramo
        mudo. Funciona igual para qualquer fonte: na Frankfurter ambos os lados
        devolvem a taxa de referência única.
        """
        tipo = TipoTaxa(tipo)  # normaliza e falha alto em valor inválido
        return self.taxa_compra if tipo is TipoTaxa.COMPRA else self.taxa_venda

    @classmethod
    def de_ptax(
        cls,
        *,
        moeda: Moeda,
        data_referencia: date,
        taxa_compra: object,
        taxa_venda: object,
        timestamp: datetime | None = None,
    ) -> "CotacaoNormalizada":
        """Constrói a partir das cotações de compra e venda do BCB (PTAX)."""
        return cls(
            fonte=Fonte.PTAX,
            moeda=moeda,
            data_referencia=data_referencia,
            timestamp=timestamp,
            taxa_compra=taxa_compra,
            taxa_venda=taxa_venda,
            possui_spread=True,
        )

    @classmethod
    def de_frankfurter(
        cls,
        *,
        moeda: Moeda,
        data_referencia: date,
        taxa: object,
        timestamp: datetime | None = None,
    ) -> "CotacaoNormalizada":
        """Constrói a partir da taxa de referência única da Frankfurter (sem spread)."""
        return cls(
            fonte=Fonte.FRANKFURTER,
            moeda=moeda,
            data_referencia=data_referencia,
            timestamp=timestamp,
            taxa_compra=taxa,
            taxa_venda=taxa,
            possui_spread=False,
        )
