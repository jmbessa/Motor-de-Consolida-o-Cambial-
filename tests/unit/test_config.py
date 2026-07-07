"""Testes da configuração (pydantic-settings)."""

from pathlib import Path

from motor_cambial.config import Config


def test_config_tem_defaults():
    c = Config()
    assert c.frankfurter_base_url.startswith("https://")
    assert "bcb.gov.br" in c.ptax_base_url
    assert c.http_timeout_s > 0
    assert c.http_max_retries >= 0
    assert isinstance(c.cache_dir, Path)
    assert c.modo_live is False


def test_config_sobrescreve_por_env(monkeypatch):
    monkeypatch.setenv("MOTOR_MODO_LIVE", "true")
    monkeypatch.setenv("MOTOR_HTTP_TIMEOUT_S", "3.5")
    c = Config()
    assert c.modo_live is True
    assert c.http_timeout_s == 3.5


def test_config_tem_janela_fallback_default():
    c = Config()
    assert c.janela_fallback_dias == 7


def test_config_janela_fallback_sobrescreve_por_env(monkeypatch):
    monkeypatch.setenv("MOTOR_JANELA_FALLBACK_DIAS", "3")
    c = Config()
    assert c.janela_fallback_dias == 3


def test_config_tem_defaults_de_db():
    c = Config()
    assert c.db_host == "db"
    assert c.db_port == 3306
    assert c.db_name == "motor_cambial"


def test_config_db_url_monta_string_sqlalchemy():
    c = Config(db_host="localhost", db_port=3307, db_user="u", db_password="p", db_name="x")
    assert c.db_url() == "mysql+pymysql://u:p@localhost:3307/x"


def test_config_db_sobrescreve_por_env(monkeypatch):
    monkeypatch.setenv("MOTOR_DB_HOST", "outro-host")
    monkeypatch.setenv("MOTOR_DB_PORT", "5306")
    c = Config()
    assert c.db_host == "outro-host"
    assert c.db_port == 5306
