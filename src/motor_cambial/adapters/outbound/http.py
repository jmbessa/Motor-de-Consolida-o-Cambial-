"""Cliente HTTP resiliente: timeout + retry em falha transitória.

Parseia todo JSON com ``parse_float=Decimal`` para que nenhum número monetário
seja representado por ``float``.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import httpx

from motor_cambial.domain.errors import FonteIndisponivel, RespostaInvalida


def obter_json(client: httpx.Client, url: str, *, max_retries: int = 2) -> Any:
    """GET em ``url`` retornando o JSON parseado (números como ``Decimal``).

    Retenta em falha transitória (timeout, erro de transporte, HTTP 5xx) até
    ``max_retries`` vezes. Levanta ``FonteIndisponivel`` se esgotar as
    tentativas, ou ``RespostaInvalida`` se o corpo não for JSON válido. Status
    4xx **não** são retentados: o corpo é retornado para o chamador decidir
    (ex.: 404 "not found").
    """
    ultima: Exception | None = None
    for _ in range(max_retries + 1):
        try:
            resposta = client.get(url)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            ultima = exc
            continue
        if resposta.status_code >= 500:
            ultima = FonteIndisponivel(f"HTTP {resposta.status_code} em {url}")
            continue
        try:
            return json.loads(resposta.text, parse_float=Decimal)
        except (ValueError, json.JSONDecodeError) as exc:
            raise RespostaInvalida(f"resposta não-JSON de {url}") from exc
    raise FonteIndisponivel(
        f"fonte indisponível após {max_retries + 1} tentativas: {url}"
    ) from ultima
