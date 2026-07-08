"""Testes da CLI (typer.testing.CliRunner) — sem rede/DB, dependências fake."""

from datetime import date
from decimal import Decimal

from typer.testing import CliRunner

from motor_cambial.adapters.inbound.cli.app import app
from motor_cambial.domain.enums import Fonte, Moeda
from motor_cambial.domain.models import CotacaoNormalizada
from motor_cambial.domain.resultado_consolidacao import ResultadoConsolidacao
from motor_cambial.domain.services.consolidador import consolidar

runner = CliRunner()


class _ProviderFake:
    def __init__(self, fonte, cotacoes=None, erro=None):
        self.fonte = fonte
        self._cotacoes = cotacoes or []
        self._erro = erro

    def buscar_cotacoes(self, moeda, data_inicial, data_final):
        if self._erro is not None:
            raise self._erro
        return self._cotacoes


class _RepoFake:
    def __init__(self):
        self.salvos = []

    def salvar(self, resultado):
        self.salvos.append(resultado)

    def buscar(self, data_referencia, hash_conjunto):
        return None

    def buscar_historico(self, data_referencia, hash_conjunto):
        return ()


def _cotacao_ptax(data_ref, compra="5.00", venda="5.10"):
    return CotacaoNormalizada.de_ptax(
        moeda=Moeda.USD, data_referencia=data_ref, taxa_compra=compra, taxa_venda=venda
    )


def _cotacao_frankfurter(data_ref, taxa="5.05"):
    return CotacaoNormalizada.de_frankfurter(
        moeda=Moeda.USD, data_referencia=data_ref, taxa=taxa
    )


def _providers_ok(data_ref):
    return {
        Fonte.PTAX: _ProviderFake(Fonte.PTAX, [_cotacao_ptax(data_ref)]),
        Fonte.FRANKFURTER: _ProviderFake(Fonte.FRANKFURTER, [_cotacao_frankfurter(data_ref)]),
    }


def _arquivo_exposicoes(tmp_path):
    arquivo = tmp_path / "exposicoes.json"
    arquivo.write_text(
        '[{"id": "1", "tipo": "payable", "moeda": "USD", "valor": "1000", '
        '"vencimento": "2026-06-05"}]',
        encoding="utf-8",
    )
    return arquivo


def test_comando_feliz_imprime_relatorio_e_exporta_json(tmp_path, monkeypatch):
    data_ref = date(2026, 6, 5)
    repo = _RepoFake()
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_providers",
        lambda config: _providers_ok(data_ref),
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_repository",
        lambda config: repo,
    )
    saida = tmp_path / "saida.json"
    resultado = runner.invoke(
        app,
        [
            "--arquivo", str(_arquivo_exposicoes(tmp_path)),
            "--data", "2026-06-05",
            "--saida", str(saida),
        ],
    )
    assert resultado.exit_code == 0, resultado.output
    assert "Motor de Consolidação Cambial" in resultado.output
    assert saida.exists()
    assert len(repo.salvos) == 1


def test_arquivo_ausente_vira_exit_code_1(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_providers",
        lambda config: _providers_ok(date(2026, 6, 5)),
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_repository",
        lambda config: _RepoFake(),
    )
    resultado = runner.invoke(
        app,
        ["--arquivo", str(tmp_path / "nao-existe.json"), "--data", "2026-06-05"],
    )
    assert resultado.exit_code == 1
    assert "erro" in resultado.output.lower()


def test_data_default_e_hoje_quando_omitida(tmp_path, monkeypatch):
    capturado = {}

    def _fake_reprocessar(
        exposicoes, providers, data_referencia, repository, config_alerta, janela_dias
    ):
        capturado["data"] = data_referencia
        return ResultadoConsolidacao(
            data_referencia=data_referencia, hash_conjunto="a" * 64,
            posicoes=(), visao=consolidar([]),
        )

    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_providers", lambda config: {}
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_repository",
        lambda config: _RepoFake(),
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.reprocessar_por_data",
        _fake_reprocessar,
    )
    saida = tmp_path / "saida.json"
    resultado = runner.invoke(
        app,
        ["--arquivo", str(_arquivo_exposicoes(tmp_path)), "--saida", str(saida)],
    )
    assert resultado.exit_code == 0, resultado.output
    assert capturado["data"] == date.today()


def test_limite_percentual_customizado_e_repassado(tmp_path, monkeypatch):
    capturado = {}

    def _fake_reprocessar(
        exposicoes, providers, data_referencia, repository, config_alerta, janela_dias
    ):
        capturado["config_alerta"] = config_alerta
        return ResultadoConsolidacao(
            data_referencia=data_referencia, hash_conjunto="a" * 64,
            posicoes=(), visao=consolidar([]),
        )

    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_providers", lambda config: {}
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_repository",
        lambda config: _RepoFake(),
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.reprocessar_por_data", _fake_reprocessar
    )
    saida = tmp_path / "saida.json"
    resultado = runner.invoke(
        app,
        [
            "--arquivo", str(_arquivo_exposicoes(tmp_path)),
            "--data", "2026-06-05",
            "--limite-percentual", "3.0",
            "--saida", str(saida),
        ],
    )
    assert resultado.exit_code == 0, resultado.output
    assert capturado["config_alerta"].limite_percentual == Decimal("3.0")


def test_saida_default_usa_convencao_data_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_ref = date(2026, 6, 5)
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_providers",
        lambda config: _providers_ok(data_ref),
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_repository",
        lambda config: _RepoFake(),
    )
    arquivo = _arquivo_exposicoes(tmp_path)
    resultado = runner.invoke(
        app, ["--arquivo", str(arquivo), "--data", "2026-06-05"]
    )
    assert resultado.exit_code == 0, resultado.output
    esperado = tmp_path / "data" / "output" / "consolidacao_2026-06-05.json"
    assert esperado.exists()


def test_data_invalida_e_rejeitada_pelo_parser(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_providers", lambda config: {}
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_repository",
        lambda config: _RepoFake(),
    )
    resultado = runner.invoke(
        app,
        ["--arquivo", str(_arquivo_exposicoes(tmp_path)), "--data", "05/06/2026"],
    )
    assert resultado.exit_code == 2
    assert "data inválida" in resultado.output.lower()


def test_limite_percentual_invalido_e_rejeitado_pelo_parser(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_providers", lambda config: {}
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_repository",
        lambda config: _RepoFake(),
    )
    resultado = runner.invoke(
        app,
        [
            "--arquivo", str(_arquivo_exposicoes(tmp_path)),
            "--data", "2026-06-05",
            "--limite-percentual", "-1",
        ],
    )
    assert resultado.exit_code == 2
    assert "positivo" in resultado.output.lower()


def test_janela_dias_negativa_e_rejeitada_pelo_parser(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_providers", lambda config: {}
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_repository",
        lambda config: _RepoFake(),
    )
    resultado = runner.invoke(
        app,
        [
            "--arquivo", str(_arquivo_exposicoes(tmp_path)),
            "--data", "2026-06-05",
            "--janela-dias", "-1",
        ],
    )
    assert resultado.exit_code == 2


def _resultado_vazio(*args, **kwargs):
    return ResultadoConsolidacao(
        data_referencia=date(2026, 6, 5), hash_conjunto="a" * 64,
        posicoes=(), visao=consolidar([]),
    )


def test_forcar_saida_utf8_reconfigura_streams(monkeypatch):
    from motor_cambial.adapters.inbound.cli import app as app_module

    class _StreamFake:
        def __init__(self):
            self.encoding_pedido = None

        def reconfigure(self, encoding):
            self.encoding_pedido = encoding

    fake_out, fake_err = _StreamFake(), _StreamFake()
    monkeypatch.setattr("sys.stdout", fake_out)
    monkeypatch.setattr("sys.stderr", fake_err)
    app_module._forcar_saida_utf8()
    assert fake_out.encoding_pedido == "utf-8"
    assert fake_err.encoding_pedido == "utf-8"


def test_forcar_saida_utf8_ignora_stream_sem_reconfigure(monkeypatch):
    from motor_cambial.adapters.inbound.cli import app as app_module

    monkeypatch.setattr("sys.stdout", object())
    monkeypatch.setattr("sys.stderr", object())
    app_module._forcar_saida_utf8()  # não deve levantar


def test_modo_live_lido_do_env_quando_flag_omitida(tmp_path, monkeypatch):
    capturado = {}
    monkeypatch.setenv("MOTOR_MODO_LIVE", "true")

    def _fake_providers(config):
        capturado["modo_live"] = config.modo_live
        return {}

    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_providers", _fake_providers
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_repository",
        lambda config: _RepoFake(),
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.reprocessar_por_data", _resultado_vazio
    )
    saida = tmp_path / "saida.json"
    resultado = runner.invoke(
        app,
        ["--arquivo", str(_arquivo_exposicoes(tmp_path)), "--data", "2026-06-05",
         "--saida", str(saida)],
    )
    assert resultado.exit_code == 0, resultado.output
    assert capturado["modo_live"] is True


def test_flag_cache_sobrepoe_env_modo_live(tmp_path, monkeypatch):
    capturado = {}
    monkeypatch.setenv("MOTOR_MODO_LIVE", "true")

    def _fake_providers(config):
        capturado["modo_live"] = config.modo_live
        return {}

    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_providers", _fake_providers
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_repository",
        lambda config: _RepoFake(),
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.reprocessar_por_data", _resultado_vazio
    )
    saida = tmp_path / "saida.json"
    resultado = runner.invoke(
        app,
        ["--arquivo", str(_arquivo_exposicoes(tmp_path)), "--data", "2026-06-05",
         "--cache", "--saida", str(saida)],
    )
    assert resultado.exit_code == 0, resultado.output
    assert capturado["modo_live"] is False


def test_janela_dias_lida_do_env_quando_flag_omitida(tmp_path, monkeypatch):
    capturado = {}
    monkeypatch.setenv("MOTOR_JANELA_FALLBACK_DIAS", "3")

    def _fake_reprocessar(
        exposicoes, providers, data_referencia, repository, config_alerta, janela_dias
    ):
        capturado["janela"] = janela_dias
        return _resultado_vazio()

    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_providers", lambda config: {}
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_repository",
        lambda config: _RepoFake(),
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.reprocessar_por_data", _fake_reprocessar
    )
    saida = tmp_path / "saida.json"
    resultado = runner.invoke(
        app,
        ["--arquivo", str(_arquivo_exposicoes(tmp_path)), "--data", "2026-06-05",
         "--saida", str(saida)],
    )
    assert resultado.exit_code == 0, resultado.output
    assert capturado["janela"] == 3


def test_flag_janela_dias_sobrepoe_env(tmp_path, monkeypatch):
    capturado = {}
    monkeypatch.setenv("MOTOR_JANELA_FALLBACK_DIAS", "3")

    def _fake_reprocessar(
        exposicoes, providers, data_referencia, repository, config_alerta, janela_dias
    ):
        capturado["janela"] = janela_dias
        return _resultado_vazio()

    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_providers", lambda config: {}
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_repository",
        lambda config: _RepoFake(),
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.reprocessar_por_data", _fake_reprocessar
    )
    saida = tmp_path / "saida.json"
    resultado = runner.invoke(
        app,
        ["--arquivo", str(_arquivo_exposicoes(tmp_path)), "--data", "2026-06-05",
         "--janela-dias", "5", "--saida", str(saida)],
    )
    assert resultado.exit_code == 0, resultado.output
    assert capturado["janela"] == 5


def test_falha_ao_exportar_json_informa_que_pipeline_ja_persistiu(tmp_path, monkeypatch):
    data_ref = date(2026, 6, 5)
    repo = _RepoFake()
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_providers",
        lambda config: _providers_ok(data_ref),
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.cli.app.construir_repository",
        lambda config: repo,
    )
    # --saida aponta para um diretório existente (sem nome de arquivo) -> write_text falha.
    resultado = runner.invoke(
        app,
        [
            "--arquivo", str(_arquivo_exposicoes(tmp_path)),
            "--data", "2026-06-05",
            "--saida", str(tmp_path),
        ],
    )
    assert resultado.exit_code == 1
    assert "persistida" in resultado.output.lower()
    assert len(repo.salvos) == 1  # o pipeline realmente já salvou antes de falhar a exportação
