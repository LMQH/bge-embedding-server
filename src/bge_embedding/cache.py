"""In-process LRU embedding cache keyed by token hash (ADR-0006 / SPEC-0003)."""
import array
import hashlib
from collections import OrderedDict

from .inference import Embedding

DENSE_BYTES = 4096  # 1024 float32 values, independent of input length.
_SPARSE_PAIR_BYTES = 32  # int, float and their list slot plus bookkeeping.


def cache_key(tokens: list[int], return_sparse: bool) -> bytes:
    digest = hashlib.sha256()
    digest.update(array.array("i", tokens).tobytes())
    digest.update(b"\x01" if return_sparse else b"\x00")
    return digest.digest()


class EmbeddingCache:
    """Single-threaded (event loop) LRU bounded by an estimated byte budget.

    Stored sparse rows are handed out by reference and are read-only by
    contract: mutating a returned row would corrupt later cache hits.
    """

    def __init__(self, max_bytes: int):
        self.max_bytes = max_bytes
        self._entries: OrderedDict[
            bytes, tuple[int, array.array, list[list[int | float]] | None]] = OrderedDict()
        self.estimated_bytes = 0

    def lookup(self, tokens: list[int], return_sparse: bool) -> Embedding | None:
        key = cache_key(tokens, return_sparse)
        entry = self._entries.get(key)
        if entry is None:
            return None
        self._entries.move_to_end(key)
        _, dense, sparse = entry
        return Embedding(dense.tolist(), sparse)

    def store(self, tokens_list: list[list[int]], embeddings: list[Embedding],
              return_sparse: bool) -> None:
        for tokens, embedding in zip(tokens_list, embeddings):
            key = cache_key(tokens, return_sparse)
            sparse = embedding.sparse
            estimate = DENSE_BYTES
            if sparse is not None:
                estimate += _SPARSE_PAIR_BYTES * len(sparse)
            old = self._entries.pop(key, None)
            if old is not None:
                self.estimated_bytes -= old[0]
            if estimate > self.max_bytes:
                continue  # An oversized entry could never be evicted back into budget.
            self.estimated_bytes += estimate
            # array('f') is a lossless float32 roundtrip for values embed() produced.
            self._entries[key] = (estimate, array.array("f", embedding.dense), sparse)
            while self.estimated_bytes > self.max_bytes:
                self.estimated_bytes -= self._entries.popitem(last=False)[1][0]
