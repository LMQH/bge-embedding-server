"""Actual model checks are opt-in and use the private service configuration."""
import os

import numpy as np
import pytest

pytestmark = [pytest.mark.real, pytest.mark.skipif(os.environ.get("BGE_REAL_TESTS") != "1",
                                                reason="Set BGE_REAL_TESTS=1 for real weights")]


def test_real_embedder_single_batch_and_lengths():
    from bge_embedding.inference import Embedder
    from bge_embedding.config import load_config
    config = load_config(os.environ["BGE_CONFIG"])
    model = Embedder(config.model.path, config.mlx)
    texts = ["知识库入库", "How do plants use sunlight?"]
    ids = model.tokenize(texts)
    batch = np.asarray([item.dense for item in model.embed(ids)])
    single = np.asarray([model.embed([item])[0].dense for item in ids])
    assert batch.shape == (2, 1024) and np.isfinite(batch).all()
    assert np.max(np.abs(np.linalg.norm(batch, axis=1) - 1)) <= 1e-5
    assert np.all(np.sum(batch * single, axis=1) >= 0.9999)

    sparse = model.embed(ids, return_sparse=True)
    assert all(item.sparse for item in sparse)
    assert all(key.isdigit() and value > 0
               for item in sparse for key, value in item.sparse.items())
    assert all(int(key) not in model.special_ids
               for item in sparse for key in item.sparse)
    assert np.array_equal(np.asarray([item.dense for item in sparse]), batch)

    for length in (8192, 8193):
        assert len(model.tokenize(["test " * (length - 2)])[0]) == length
