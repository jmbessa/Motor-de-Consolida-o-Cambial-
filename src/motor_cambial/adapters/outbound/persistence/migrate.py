"""Entrypoint de migração: aplica o schema no MySQL configurado.

Executável via ``python -m motor_cambial.adapters.outbound.persistence.migrate``.
Monta o engine a partir de ``Config`` e aplica ``criar_schema`` (idempotente —
``create_all`` não recria tabelas já existentes). Timestamps/DDL são
responsabilidade da borda; este script é operacional, não de domínio.
"""

from __future__ import annotations

from sqlalchemy import create_engine

from motor_cambial.adapters.outbound.persistence.schema import criar_schema
from motor_cambial.config import Config


def main() -> None:
    config = Config()
    engine = create_engine(config.db_url())
    try:
        criar_schema(engine)
        print(
            f"schema aplicado em "
            f"{config.db_host}:{config.db_port}/{config.db_name}"
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
