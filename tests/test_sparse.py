import numpy as np

from bge_embedding.inference import Embedder


def sparse(ids, weights, special=()):
    embedder = Embedder.__new__(Embedder)
    embedder.special_ids = set(special)
    return embedder._sparse(ids, np.asarray(weights, dtype=np.float32))


def test_duplicate_tokens_keep_max_weight_and_unique_indices():
    assert sparse([7, 9, 7], [0.5, 0.25, 0.75]) == [[7, 0.75], [9, 0.25]]


def test_drops_special_tokens_and_non_positive_weights():
    assert sparse([0, 4, 5], [0.9, 0.0, 0.1], special={0, 4}) == [[5, float(np.float32(0.1))]]


def test_returns_integer_ids_and_float_weights_in_first_seen_order():
    result = sparse([250001, 1], [0.25, 0.5])
    assert result == [[250001, 0.25], [1, 0.5]]
    assert all(type(token_id) is int and type(weight) is float for token_id, weight in result)


def test_weights_are_float32_values_as_python_floats():
    result = sparse([3], [0.1])
    assert result == [[3, float(np.float32(0.1))]]
