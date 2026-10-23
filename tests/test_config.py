from dataclasses import replace
import json
import sys

import pytest

from bge_embedding.config import load_config


@pytest.mark.parametrize("before, after", [
    ('port = 8000', 'port = 0'),
    ('port = 8000', 'port = 65536'),
    ('port = 8000', 'port = true'),
    ('port = 8000', 'port = "8000"'),
    ('max_waiting = 19', 'max_waiting = -1'),
    ('wait_timeout_seconds = 30.0', 'wait_timeout_seconds = nan'),
    ('wait_timeout_seconds = 30.0', 'wait_timeout_seconds = 0'),
    ('max_body_bytes = 1048576', 'max_body_bytes = 0'),
    ('max_batch_size = 16', 'max_batch_size = false'),
    ('max_tokens_per_text = 8192', 'max_tokens_per_text = 8193'),
    ('max_tokens_per_request = 32768', 'max_tokens_per_request = -1'),
    ('memory_limit_bytes = 2147483648', 'memory_limit_bytes = 0'),
    ('cache_limit_bytes = 268435456', 'cache_limit_bytes = -1'),
    ('max_bytes = 5242880', 'max_bytes = 0'),
    ('backup_count = 2', 'backup_count = 0'),
    ('level = "INFO"', 'level = "TRACE"'),
    ('host = "127.0.0.1"', 'host = " "'),
    ('path = "models/bge-m3-mlx-8bit"', 'path = "missing"'),
    ('max_waiting = 19', 'max_waitng = 19'),
    ('port = 8000\n', ''),
    ('[queue]', '[unknown]'),
    ('[server]', '[server'),
    ('enabled = true', 'enabled = "yes"'),
    ('enabled = true', 'enabled = 1'),
    ('max_bytes = 268435456', 'max_bytes = 0'),
    ('max_bytes = 268435456', 'max_bytes = 1.0'),
    ('[cache]\n', ''),
    ('enabled = true', 'enbled = true'),
])
def test_invalid_configuration_is_rejected_without_values(config_file, before, after):
    config_file.write_text(config_file.read_text().replace(before, after))
    with pytest.raises(ValueError) as error:
        load_config(config_file)
    assert "test-key-sentinel-950d" not in str(error.value)


def test_cache_configuration_loads(settings):
    assert settings.cache.enabled is True
    assert settings.cache.max_bytes == 268435456


def test_paths_resolve_from_configuration_directory(config_file, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path.parent)
    config = load_config(config_file)
    assert config.model.path == str(tmp_path / "models/bge-m3-mlx-8bit")
    assert config.logging.file == str(tmp_path / "logs/service.log")


def test_model_metadata_bounds_configuration(config_file):
    model = config_file.parent / "models/bge-m3-mlx-8bit"
    (model / "config.json").write_text(json.dumps({"max_position_embeddings": 4098, "pad_token_id": 1}))
    with pytest.raises(ValueError, match="model context length"):
        load_config(config_file)
    (model / "model.safetensors").unlink()
    with pytest.raises(ValueError, match="Local model files"):
        load_config(config_file)


def test_startup_uses_configuration(settings, monkeypatch):
    from bge_embedding import __main__ as entry
    calls = {}

    class FakeServer:
        started = True

        def __init__(self, config):
            calls["server"] = config

        def run(self):
            calls["run"] = True

    config = replace(settings, server=replace(settings.server, host="127.0.0.2", port=8123))
    monkeypatch.setattr(sys, "argv", ["bge_embedding", "--config", "private.toml"])
    monkeypatch.setattr(entry, "load_config", lambda path: config)
    monkeypatch.setattr(entry, "configure_logging", lambda value: calls.update(logging=value))
    monkeypatch.setattr(entry, "Server", FakeServer)
    monkeypatch.setenv("BGE_PORT", "9999")
    monkeypatch.setenv("BGE_HOST", "ignored")
    assert entry.main() == 0
    assert calls["server"].host == "127.0.0.2" and calls["server"].port == 8123
    assert calls["server"].workers == 1 and calls["run"]
    assert calls["logging"] == config.logging


def test_invalid_file_fails_before_server_start(config_file, monkeypatch, capsys):
    from bge_embedding import __main__ as entry
    config_file.write_text('[auth]\napi_key = "secret-do-not-echo"\ninvalid = [')
    monkeypatch.setattr(sys, "argv", ["bge_embedding", "--config", str(config_file)])
    assert entry.main() == 1
    assert "secret-do-not-echo" not in capsys.readouterr().err


def test_configured_mlx_limits_reach_runtime(settings, monkeypatch):
    from types import SimpleNamespace
    import mlx_embeddings
    from bge_embedding import inference
    calls = {}
    model = SimpleNamespace(encoder=SimpleNamespace(layer=[]), eval=lambda: None)
    tokenizer = SimpleNamespace(all_special_ids=[0, 1, 2, 3], pad_token_id=1)
    monkeypatch.setattr(mlx_embeddings, "load", lambda *args, **kwargs: (model, tokenizer))
    monkeypatch.setattr(inference.mx, "set_memory_limit", lambda value: calls.update(memory=value))
    monkeypatch.setattr(inference.mx, "set_cache_limit", lambda value: calls.update(cache=value))
    config = replace(settings.mlx, memory_limit_bytes=1024**3, cache_limit_bytes=64 * 1024**2)
    inference.Embedder(settings.model.path, config)
    assert calls == {"memory": 1024**3, "cache": 64 * 1024**2}


def test_missing_sparse_head_fails_before_model_load(tmp_path):
    from types import SimpleNamespace
    from bge_embedding.inference import Embedder
    model = tmp_path / "model"
    model.mkdir()
    (model / "model.safetensors").touch()
    with pytest.raises(ValueError, match="sparse head"):
        Embedder(str(model), SimpleNamespace(memory_limit_bytes=1, cache_limit_bytes=1))
