"""Configuração da aplicação (defaults versionados + override por env var)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Settings do motor. Env vars usam o prefixo ``MOTOR_`` (ex.: MOTOR_MODO_LIVE)."""

    model_config = SettingsConfigDict(env_prefix="MOTOR_", env_file=".env", extra="ignore")

    ptax_base_url: str = (
        "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"
    )
    frankfurter_base_url: str = "https://api.frankfurter.app"
    http_timeout_s: float = 10.0
    http_max_retries: int = 2
    cache_dir: Path = Path("data/cache")
    modo_live: bool = False
    janela_fallback_dias: int = 7

    # Persistência (Fatia 6a/6b). Defaults apontam para o serviço `db` do compose;
    # a senha é um default de desenvolvimento, sobrescrivível por MOTOR_DB_PASSWORD.
    db_host: str = "db"
    db_port: int = 3306
    db_user: str = "motor"
    db_password: str = "motor"
    db_name: str = "motor_cambial"

    def db_url(self) -> str:
        """URL de conexão SQLAlchemy (driver PyMySQL)."""
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
