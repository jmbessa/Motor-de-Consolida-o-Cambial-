"""Normalização de payloads da Frankfurter para CotacaoNormalizada (puro)."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import ValidationError

from motor_cambial.domain.enums import Moeda
from motor_cambial.domain.errors import MoedaNaoSuportadaPelaFonte, RespostaInvalida
from motor_cambial.domain.models import CotacaoNormalizada


def normalizar_frankfurter(payload: dict[str, Any], moeda: Moeda) -> list[CotacaoNormalizada]:
    """Converte o corpo do endpoint de intervalo em cotações normalizadas.

    ``rates`` tem a forma ``{data_iso: {"BRL": taxa}}`` (endpoint de intervalo).
    Moeda inexistente vem como ``{"message": "not found"}`` -> erro.
    """
    if not isinstance(payload, dict):
        raise RespostaInvalida(f"payload Frankfurter não é um objeto JSON: {payload!r}")

    if "rates" not in payload:
        if "message" in payload:
            raise MoedaNaoSuportadaPelaFonte(
                f"Frankfurter não fornece {moeda.value}: {payload['message']}"
            )
        raise RespostaInvalida(f"payload Frankfurter sem 'rates': {payload!r}")

    rates = payload["rates"]
    if not isinstance(rates, dict):
        raise RespostaInvalida(f"payload Frankfurter com 'rates' não-dict: {rates!r}")

    cotacoes: list[CotacaoNormalizada] = []
    for data_iso, valores in rates.items():
        try:
            data_ref = date.fromisoformat(data_iso)
            taxa = valores["BRL"]
            cotacoes.append(
                CotacaoNormalizada.de_frankfurter(
                    moeda=moeda, data_referencia=data_ref, taxa=taxa
                )
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise RespostaInvalida(
                f"entrada malformada na Frankfurter: {data_iso}={valores!r}"
            ) from exc
    return sorted(cotacoes, key=lambda c: c.data_referencia)
