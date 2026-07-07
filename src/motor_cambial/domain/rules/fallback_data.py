"""Regra de fallback de data (requisito 6.10).

Direção: backward — usa a cotação do último dia disponível anterior ou igual
à data solicitada. Forward-fill usaria dado "do futuro" em relação à
data-valor, incorreto para tesouraria. Se nenhuma data disponível cair dentro
da janela configurada, levanta ``SemCotacaoNaJanela`` em vez de usar uma taxa
silenciosamente defasada além do limite.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict, Field, model_validator

from motor_cambial.domain.errors import SemCotacaoNaJanela


class ResultadoFallback(BaseModel):
    """Data efetiva usada numa conversão, com rastreabilidade do fallback."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data_efetiva: date
    houve_fallback: bool
    defasagem_dias: int = Field(ge=0)

    @model_validator(mode="after")
    def _valida_coerencia(self) -> "ResultadoFallback":
        if self.houve_fallback != (self.defasagem_dias > 0):
            raise ValueError(
                "houve_fallback deve ser True se e somente se defasagem_dias > 0"
            )
        return self


def resolver_data_efetiva(
    data_solicitada: date,
    datas_disponiveis: Collection[date],
    janela_dias: int = 7,
) -> ResultadoFallback:
    """Retrocede a partir de ``data_solicitada`` até achar uma cotação.

    Percorre ``data_solicitada``, ``data_solicitada - 1 dia``, ... até
    ``data_solicitada - janela_dias`` (inclusive). Levanta
    ``SemCotacaoNaJanela`` se nenhuma dessas datas estiver em
    ``datas_disponiveis``.
    """
    if janela_dias < 0:
        raise ValueError("janela_dias deve ser >= 0")
    disponiveis = set(datas_disponiveis)
    for defasagem in range(janela_dias + 1):
        candidata = data_solicitada - timedelta(days=defasagem)
        if candidata in disponiveis:
            return ResultadoFallback(
                data_efetiva=candidata,
                houve_fallback=defasagem > 0,
                defasagem_dias=defasagem,
            )
    raise SemCotacaoNaJanela(
        f"nenhuma cotação disponível para {data_solicitada.isoformat()} "
        f"nem nos {janela_dias} dias corridos anteriores"
    )
