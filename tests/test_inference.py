"""Actual model checks are opt-in and use the private service configuration."""
import math
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
    assert all(isinstance(token_id, int) and 0 <= token_id < 2**32 - 1 and value > 0
               for item in sparse for token_id, value in item.sparse)
    assert all(token_id not in model.special_ids
               for item in sparse for token_id, _ in item.sparse)
    assert all(len({token_id for token_id, _ in item.sparse}) == len(item.sparse)
               for item in sparse)
    assert np.array_equal(np.asarray([item.dense for item in sparse]), batch)

    for length in (8192, 8193):
        assert len(model.tokenize(["test " * (length - 2)])[0]) == length


def test_real_embedder_varied_length_batches_match_single():
    from bge_embedding.inference import Embedder
    from bge_embedding.config import load_config
    config = load_config(os.environ["BGE_CONFIG"])
    model = Embedder(config.model.path, config.mlx)
    lengths = [25, 64, 256, 512, 1024, 25, 128]
    ids = model.tokenize(["test " * (length - 2) for length in lengths])

    batch = np.asarray([item.dense for item in model.embed(ids)])
    single = np.asarray([model.embed([item])[0].dense for item in ids])
    assert batch.shape == (len(lengths), 1024) and np.isfinite(batch).all()
    assert np.max(np.abs(np.linalg.norm(batch, axis=1) - 1)) <= 1e-5
    assert np.all(np.sum(batch * single, axis=1) >= 0.999999)

    sparse_batch = model.embed(ids, return_sparse=True)
    sparse_single = [model.embed([item], return_sparse=True)[0] for item in ids]
    for batched, alone in zip(sparse_batch, sparse_single):
        assert dict(batched.sparse).keys() == dict(alone.sparse).keys()
        alone_weights = dict(alone.sparse)
        for token_id, value in batched.sparse:
            assert math.isclose(value, alone_weights[token_id],
                                rel_tol=2e-3, abs_tol=5e-4)
