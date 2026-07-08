"""Entrypoint de migração: aplica o schema no MySQL configurado.

Executável via ``python -m motor_cambial.adapters.outbound.persistence.migrate``.
Monta o engine a partir de ``Config`` e aplica ``criar_schema`` — que usa
``create_all``: **cria tabelas ausentes, mas NÃO altera tabelas existentes**.
Não há versionamento de migração (Alembic é over-engineering para o escopo);
uma mudança futura de schema exige recriar o volume (``make clean``). Timestamps
e DDL são responsabilidade da borda; este script é operacional, não de domínio.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from motor_cambial.adapters.outbound.persistence.schema import criar_schema
from motor_cambial.config import Config


def main() -> None:
    config = Config()
    engine = create_engine(config.db_url())
    try:
        criar_schema(engine)
    except OperationalError as exc:
        raise SystemExit(
            f"não foi possível conectar ao MySQL em "
            f"{config.db_host}:{config.db_port}/{config.db_name}. "
            f"O container está no ar? Rode `make up`.\nDetalhe: {exc}"
        ) from exc
    finally:
        engine.dispose()
    print(
        f"schema garantido em {config.db_host}:{config.db_port}/{config.db_name} "
        f"(tabelas criadas se ausentes)"
    )


if __name__ == "__main__":
    main()
