"""Client HTTP da Frankfurter (adapter outbound)."""

from __future__ import annotations

from datetime import date

import httpx

from motor_cambial.adapters.outbound.frankfurter.normalizer import (
    normalizar_frankfurter,
)
from motor_cambial.adapters.outbound.http import obter_json
from motor_cambial.domain.enums import Fonte, Moeda
from motor_cambial.domain.models import CotacaoNormalizada


class FrankfurterProvider:
    """Busca cotações na Frankfurter (endpoint de intervalo, moeda -> BRL)."""

    fonte = Fonte.FRANKFURTER

    def __init__(
        self, client: httpx.Client, base_url: str, max_retries: int = 2
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries

    def buscar_cotacoes(
        self, moeda: Moeda, data_inicial: date, data_final: date
    ) -> list[CotacaoNormalizada]:
        url = (
            f"{self._base_url}/{data_inicial.isoformat()}..{data_final.isoformat()}"
            f"?from={moeda.value}&to=BRL"
        )
        payload = obter_json(self._client, url, max_retries=self._max_retries)
        return normalizar_frankfurter(payload, moeda)
