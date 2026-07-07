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
