import json
from pathlib import Path

import pytest

from bge_embedding.config import load_config


@pytest.fixture
def config_file(tmp_path):
    model = tmp_path / "models/bge-m3-mlx-8bit"
    model.mkdir(parents=True)
    (model / "model.safetensors").touch()
    (model / "config.json").write_text(json.dumps({"max_position_embeddings": 8194, "pad_token_id": 1}))
    (model / "tokenizer_config.json").write_text(json.dumps({"model_max_length": 8192}))
    template = (Path(__file__).resolve().parents[1] / "config.example.toml").read_text()
    template = template.replace('api_key = ""', 'api_key = "test-key-sentinel-950d"')
    target = tmp_path / "config.toml"
    target.write_text(template)
    target.chmod(0o600)
    return target


@pytest.fixture
def settings(config_file):
    return load_config(config_file)
