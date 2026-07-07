"""Decorator de cache (memória + arquivo JSON) sobre um CotacaoProvider."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from motor_cambial.domain.enums import Fonte, Moeda
from motor_cambial.domain.models import CotacaoNormalizada
from motor_cambial.ports.cotacao_provider import CotacaoProvider


class CacheCotacaoProvider:
    """Envolve um provider, servindo de cache por (fonte, moeda, janela).

    Persiste em ``{cache_dir}/{fonte}.json``. Com ``modo_live=True``, ignora o
    cache na leitura e sempre rebusca (reescrevendo a entrada).
    """

    def __init__(
        self, inner: CotacaoProvider, cache_dir: Path, modo_live: bool = False
    ) -> None:
        self.fonte: Fonte = inner.fonte
        self._inner = inner
        self._modo_live = modo_live
        self._cache_dir = Path(cache_dir)
        self._arquivo = self._cache_dir / f"{self.fonte.value}.json"
        self._memoria: dict[str, list[dict]] = self._carregar()

    def _carregar(self) -> dict[str, list[dict]]:
        if self._arquivo.exists():
            return json.loads(self._arquivo.read_text(encoding="utf-8"))
        return {}

    def _salvar(self) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._arquivo.write_text(
            json.dumps(self._memoria, ensure_ascii=False), encoding="utf-8"
        )

    @staticmethod
    def _chave(moeda: Moeda, data_inicial: date, data_final: date) -> str:
        return f"{moeda.value}|{data_inicial.isoformat()}|{data_final.isoformat()}"

    def buscar_cotacoes(
        self, moeda: Moeda, data_inicial: date, data_final: date
    ) -> list[CotacaoNormalizada]:
        chave = self._chave(moeda, data_inicial, data_final)
        if not self._modo_live and chave in self._memoria:
            return [CotacaoNormalizada.model_validate(d) for d in self._memoria[chave]]
        cotacoes = self._inner.buscar_cotacoes(moeda, data_inicial, data_final)
        self._memoria[chave] = [c.model_dump(mode="json") for c in cotacoes]
        self._salvar()
        return cotacoes
