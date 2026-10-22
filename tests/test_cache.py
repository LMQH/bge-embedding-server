from bge_embedding.cache import EmbeddingCache, DENSE_BYTES, cache_key
from bge_embedding.inference import Embedding


def embedding(sparse=None):
    return Embedding([0.5] * 1024, sparse)


def test_key_distinguishes_tokens_and_flag():
    assert cache_key([1, 2], False) == cache_key([1, 2], False)
    assert cache_key([1, 2], False) != cache_key([1, 2], True)
    assert cache_key([1, 2], False) != cache_key([2, 1], False)
    assert cache_key([1, 2, 3], False) != cache_key([1, 2], False)


def test_lookup_miss_then_hit_roundtrip():
    cache = EmbeddingCache(1 << 20)
    assert cache.lookup([1, 2], False) is None
    cache.store([[1, 2]], [embedding()], False)
    found = cache.lookup([1, 2], False)
    assert found == embedding()
    assert found.dense == [0.5] * 1024 and found.sparse is None


def test_sparse_flag_isolates_entries():
    cache = EmbeddingCache(1 << 20)
    cache.store([[1, 2]], [embedding({"3": 0.5})], True)
    assert cache.lookup([1, 2], False) is None
    found = cache.lookup([1, 2], True)
    assert found == embedding({"3": 0.5})


def test_lru_eviction_keeps_budget():
    cache = EmbeddingCache(DENSE_BYTES * 3)
    for i in range(4):
        cache.store([[i]], [embedding()], False)
    assert cache.estimated_bytes <= DENSE_BYTES * 3
    assert cache.lookup([0], False) is None
    assert cache.lookup([3], False) is not None


def test_lookup_refreshes_recency():
    cache = EmbeddingCache(DENSE_BYTES * 2)
    cache.store([[1]], [embedding()], False)
    cache.store([[2]], [embedding()], False)
    assert cache.lookup([1], False) is not None
    cache.store([[3]], [embedding()], False)
    assert cache.lookup([1], False) is not None
    assert cache.lookup([2], False) is None


def test_oversized_entry_is_not_cached():
    cache = EmbeddingCache(DENSE_BYTES)
    cache.store([[1]], [Embedding([0.5] * 1024, {"x" * 4096: 0.5})], True)
    assert cache.lookup([1], True) is None
    assert cache.estimated_bytes == 0


def test_sparse_entries_count_toward_budget():
    cache = EmbeddingCache(DENSE_BYTES * 2)
    for i in range(3):
        cache.store([[i]], [Embedding([0.5] * 1024, {"t" * 100: 0.5})], True)
    assert cache.lookup([0], True) is None
    assert cache.lookup([2], True) is not None


def test_duplicate_tokens_in_one_batch_store_once():
    cache = EmbeddingCache(1 << 20)
    cache.store([[7], [7]], [embedding(), embedding()], False)
    assert cache.lookup([7], False) == embedding()
    assert len(cache._entries) == 1


def test_store_refreshes_existing_entry_budget():
    cache = EmbeddingCache(DENSE_BYTES * 2)
    cache.store([[1]], [embedding()], False)
    cache.store([[2]], [embedding()], False)
    cache.store([[1]], [embedding({"k": 0.5})], False)
    assert cache.lookup([2], False) is None
    assert cache.lookup([1], False).sparse == {"k": 0.5}
    assert cache.estimated_bytes <= DENSE_BYTES * 2
