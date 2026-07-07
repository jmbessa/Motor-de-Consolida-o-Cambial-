"""Client HTTP da PTAX/BCB (adapter outbound).

USD é cotado direto contra o BRL (endpoint do dólar); as demais moedas são
cross-rates derivadas via paridade com o dólar (endpoint de moeda) — por isso
os dois caminhos. Em ambos, a PTAX já entrega cotacaoCompra/Venda em BRL, então
ignoramos os campos de paridade.
"""

from __future__ import annotations

from datetime import date

import httpx

from motor_cambial.adapters.outbound.http import obter_json
from motor_cambial.adapters.outbound.ptax.normalizer import normalizar_ptax
from motor_cambial.domain.enums import Fonte, Moeda
from motor_cambial.domain.errors import RespostaInvalida
from motor_cambial.domain.models import CotacaoNormalizada

_FORMATO_DATA = "%m-%d-%Y"  # PTAX exige MM-DD-YYYY


class PtaxProvider:
    """Busca cotações de fechamento na PTAX (dólar direto; demais via paridade)."""

    fonte = Fonte.PTAX

    def __init__(
        self, client: httpx.Client, base_url: str, max_retries: int = 2
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries

    def buscar_cotacoes(
        self, moeda: Moeda, data_inicial: date, data_final: date
    ) -> list[CotacaoNormalizada]:
        inicio = data_inicial.strftime(_FORMATO_DATA)
        fim = data_final.strftime(_FORMATO_DATA)
        if moeda is Moeda.USD:
            url = (
                f"{self._base_url}/CotacaoDolarPeriodo(dataInicial=@dataInicial,"
                f"dataFinalCotacao=@dataFinalCotacao)?@dataInicial='{inicio}'"
                f"&@dataFinalCotacao='{fim}'&$format=json"
            )
        else:
            url = (
                f"{self._base_url}/CotacaoMoedaPeriodo(moeda=@moeda,"
                f"dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)?"
                f"@moeda='{moeda.value}'&@dataInicial='{inicio}'"
                f"&@dataFinalCotacao='{fim}'&$format=json"
            )
        payload = obter_json(self._client, url, max_retries=self._max_retries)
        if not isinstance(payload, dict):
            raise RespostaInvalida(f"payload PTAX não é um objeto JSON: {payload!r}")
        value = payload.get("value")
        if not isinstance(value, list):
            raise RespostaInvalida(
                f"payload PTAX com 'value' ausente ou não-lista: {payload!r}"
            )
        return normalizar_ptax(value, moeda)
