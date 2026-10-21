"""Targeted regression for the reported quadratic attention allocation."""
import os

import mlx.core as mx
import pytest

from bge_embedding.inference import Embedder
from bge_embedding.config import load_config


@pytest.mark.real
def test_long_input_memory():
    config = load_config(os.environ['BGE_CONFIG'])
    model = Embedder(config.model.path, config.mlx)
    ids = model.tokenize(['test ' * 2046])
    assert len(ids[0]) == 2048
    mx.clear_cache()
    mx.reset_peak_memory()
    model.embed(ids)
    peak = mx.get_peak_memory()
    assert peak < 1280 * 1024**2, f'2048-token Metal allocation peak: {peak / 1024**2:.1f} MiB'
