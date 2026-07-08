"""Carrega exposições cambiais de um arquivo JSON local (requisito do enunciado).

Formato esperado: uma lista de objetos, cada um com os campos de ``Exposicao``
(``valor`` como string, para preservar precisão Decimal na leitura). Qualquer
desvio do formato — arquivo ausente, JSON inválido, não é uma lista, item que
falha a validação de ``Exposicao`` — vira ``RespostaInvalida`` (reuso do erro
de domínio já usado para dado malformado de fonte externa), com o índice do
item problemático quando aplicável.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from motor_cambial.domain.errors import RespostaInvalida
from motor_cambial.domain.models import Exposicao


def carregar_exposicoes(caminho: Path) -> list[Exposicao]:
    """Lê e valida a lista de exposições do arquivo JSON em ``caminho``."""
    try:
        texto = caminho.read_text(encoding="utf-8")
    except OSError as exc:
        raise RespostaInvalida(
            f"não foi possível ler o arquivo de exposições {caminho!s}: {exc}"
        ) from exc

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise RespostaInvalida(
            f"arquivo de exposições {caminho!s} não é um JSON válido: {exc}"
        ) from exc

    if not isinstance(dados, list):
        raise RespostaInvalida(
            f"arquivo de exposições {caminho!s} deve conter uma lista, "
            f"recebido {type(dados).__name__}"
        )

    exposicoes: list[Exposicao] = []
    ids_vistos: set[str] = set()
    for indice, item in enumerate(dados):
        try:
            exposicao = Exposicao.model_validate(item)
        except ValidationError as exc:
            raise RespostaInvalida(
                f"exposição inválida no índice {indice} de {caminho!s}: {exc}"
            ) from exc
        if exposicao.id in ids_vistos:
            raise RespostaInvalida(
                f"id duplicado {exposicao.id!r} no índice {indice} de {caminho!s}"
            )
        ids_vistos.add(exposicao.id)
        exposicoes.append(exposicao)
    return exposicoes
