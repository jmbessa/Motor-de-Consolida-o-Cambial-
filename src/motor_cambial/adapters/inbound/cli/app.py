"""CLI do Motor de Consolidação Cambial (adapter inbound).

Comando único ``consolidar``: carrega exposições de um arquivo JSON, roda o
pipeline completo (busca cotações, consolida, persiste — via
``reprocessar_por_data``), imprime um relatório no console e exporta o
resultado completo em JSON. Fino de propósito — toda a lógica de negócio já
existe no domínio/aplicação; este módulo só orquestra I/O de borda (arquivo,
terminal) e injeta as dependências concretas via ``composition_root``.
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import typer
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from motor_cambial.adapters.inbound.cli.loader import carregar_exposicoes
from motor_cambial.adapters.inbound.cli.relatorio import formatar_relatorio
from motor_cambial.application.use_cases.reprocessar_por_data import (
    reprocessar_por_data,
)
from motor_cambial.composition_root import construir_providers, construir_repository
from motor_cambial.config import Config
from motor_cambial.domain.decimal_utils import DecimalPositivo
from motor_cambial.domain.errors import DomainError
from motor_cambial.domain.rules.alertas import ConfiguracaoAlerta

app = typer.Typer(add_completion=False)

_valida_decimal_positivo = TypeAdapter(DecimalPositivo).validate_python


def _validar_data(valor: str | None) -> str | None:
    """Callback de validação do --data: erro amigável na borda do parser, não um crash."""
    if valor is None:
        return valor
    try:
        date.fromisoformat(valor)
    except ValueError as exc:
        raise typer.BadParameter(f"data inválida, use YYYY-MM-DD: {valor!r}") from exc
    return valor


def _validar_limite(valor: str | None) -> str | None:
    """Callback de validação de --limite-percentual/--limite-absoluto: mesmo motivo."""
    if valor is None:
        return valor
    try:
        _valida_decimal_positivo(valor)
    except PydanticValidationError as exc:
        raise typer.BadParameter(f"deve ser um número positivo: {valor!r}") from exc
    return valor


@app.command()
def consolidar(
    arquivo: Path = typer.Option(
        Path("data/exposicoes.json"), "--arquivo", help="Arquivo JSON de exposições"
    ),
    data: str | None = typer.Option(
        None,
        "--data",
        help="Data de referência (YYYY-MM-DD); default: hoje",
        callback=_validar_data,
    ),
    live: bool | None = typer.Option(
        None,
        "--live/--cache",
        help="Busca ao vivo vs. cache; se omitido, usa MOTOR_MODO_LIVE (default cache)",
    ),
    limite_percentual: str | None = typer.Option(
        None,
        "--limite-percentual",
        help="Limite percentual de alerta (default: 1.5)",
        callback=_validar_limite,
    ),
    limite_absoluto: str | None = typer.Option(
        None,
        "--limite-absoluto",
        help="Limite absoluto em BRL de alerta (default: 10000)",
        callback=_validar_limite,
    ),
    janela_dias: int | None = typer.Option(
        None,
        "--janela-dias",
        min=0,
        help="Janela de fallback (dias); se omitido, usa MOTOR_JANELA_FALLBACK_DIAS (7)",
    ),
    saida: Path | None = typer.Option(
        None,
        "--saida",
        help="Caminho do JSON exportado (default: data/output/consolidacao_{data}.json)",
    ),
) -> None:
    """Consolida exposições cambiais em BRL via PTAX e Frankfurter."""
    data_referencia = date.fromisoformat(data) if data else date.today()

    overrides: dict[str, Decimal] = {}
    if limite_percentual is not None:
        overrides["limite_percentual"] = Decimal(limite_percentual)
    if limite_absoluto is not None:
        overrides["limite_absoluto_brl"] = Decimal(limite_absoluto)
    config_alerta = ConfiguracaoAlerta(**overrides)

    # Flags têm prioridade; quando omitidas (None), cai no Config (env var/default).
    config = Config() if live is None else Config(modo_live=live)
    janela = janela_dias if janela_dias is not None else config.janela_fallback_dias

    try:
        providers = construir_providers(config)
        repository = construir_repository(config)
        exposicoes = carregar_exposicoes(arquivo)
        resultado = reprocessar_por_data(
            exposicoes,
            providers,
            data_referencia,
            repository,
            config_alerta,
            janela,
        )
    except DomainError as exc:
        typer.echo(f"erro: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(formatar_relatorio(resultado))

    caminho_saida = saida or (
        Path("data/output") / f"consolidacao_{data_referencia.isoformat()}.json"
    )
    try:
        caminho_saida.parent.mkdir(parents=True, exist_ok=True)
        caminho_saida.write_text(resultado.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:
        typer.echo(
            f"aviso: consolidação processada e persistida, mas falhou ao exportar "
            f"o JSON em {caminho_saida}: {exc}",
            err=True,
        )
        raise typer.Exit(code=1)
    typer.echo(f"resultado exportado em {caminho_saida}")


def _forcar_saida_utf8() -> None:
    """Garante saída UTF-8 no console.

    No Windows, ``sys.stdout``/``stderr`` assumem o code page do sistema (ex.:
    cp1252), o que corrompe os acentos do relatório num terminal UTF-8.
    Reconfigurar para UTF-8 no entrypoint resolve sem depender de env externa.
    Streams sem ``reconfigure`` (ex.: já substituídos por um teste) são ignorados.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


if __name__ == "__main__":
    _forcar_saida_utf8()
    app()
