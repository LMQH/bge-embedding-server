"""Local-only MLX loading and explicit raw CLS pooling."""
from dataclasses import dataclass
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np


@dataclass
class Embedding:
    dense: list[float]
    # [token_id, weight] pairs, ready for a Milvus SPARSE_FLOAT_VECTOR field.
    sparse: list[list[int | float]] | None = None


# Bound one padded forward: a 16 x 512 group is exactly 8192 padded tokens.
# Larger groups showed no throughput gain on 1024+ token inputs and increased peak memory.
_BATCH_TOKEN_LIMIT = 8192
_BATCH_SIZE_LIMIT = 16
_BATCH_LENGTH_RATIO = 1.25
# FP16 fused attention is ~18-21% faster on the M4; sparse weights absorb a
# small rounding difference, bounded by the SPEC-0001 tolerance.
_ATTENTION_DTYPE = mx.float16


def batch_groups(lengths: list[int]) -> list[list[int]]:
    """Group indices by similar length within the padded-token budget."""
    order = sorted(range(len(lengths)), key=lambda index: (lengths[index], index))
    groups, current = [], []
    for index in order:
        length = lengths[index]
        if current:
            first = lengths[current[0]]
            if (len(current) >= _BATCH_SIZE_LIMIT
                    or length > first * _BATCH_LENGTH_RATIO
                    or length * (len(current) + 1) > _BATCH_TOKEN_LIMIT):
                groups.append(current)
                current = []
        current.append(index)
    if current:
        groups.append(current)
    return groups


class FusedSelfAttention(nn.Module):
    """Inference-only replacement for mlx-embeddings 0.1.0 XLM-R attention."""

    def __init__(self, original):
        super().__init__()
        self.query, self.key, self.value = original.query, original.key, original.value
        self.num_heads = original.num_attention_heads
        self.head_dim = original.attention_head_size

    def __call__(self, x, attention_mask=None, head_mask=None, output_attentions=False):
        if self.training or head_mask is not None or output_attentions:
            raise ValueError("Only embedding inference is supported.")
        batch, length, _ = x.shape

        def project(layer):
            projected = layer(x).reshape(batch, length, self.num_heads, self.head_dim)
            return projected.transpose(0, 2, 1, 3).astype(_ATTENTION_DTYPE)

        # Additive padding mask, never causal: BGE uses bidirectional attention.
        # Keep the mask in the attention dtype so SDPA does not promote back to FP32.
        mask = (attention_mask.astype(_ATTENTION_DTYPE)
                if attention_mask is not None else None)
        context = mx.fast.scaled_dot_product_attention(
            project(self.query), project(self.key), project(self.value),
            scale=self.head_dim ** -0.5, mask=mask, force_fused=True)
        # Bound graph liveness across the 24 layers, not just attention scores.
        mx.eval(context)
        return (context.transpose(0, 2, 1, 3).reshape(batch, length, -1),)


class Embedder:
    def __init__(self, model_path: str, config):
        from mlx_embeddings import load

        path = Path(model_path).expanduser().resolve()
        if not path.is_dir() or not (path / "model.safetensors").is_file():
            raise ValueError("Local model files are required.")
        if not (path / "sparse_linear.safetensors").is_file():
            raise ValueError("Local sparse head is required.")
        if not mx.metal.is_available():
            raise RuntimeError("Metal is required.")
        mx.set_default_device(mx.gpu)
        # Guidelines, not an OS hard quota; measured on the M4 at 8192 tokens.
        mx.set_memory_limit(config.memory_limit_bytes)
        mx.set_cache_limit(config.cache_limit_bytes)
        self.model, self.tokenizer = load(
            str(path), tokenizer_config={"padding_side": "right", "local_files_only": True})
        for layer in self.model.encoder.layer:
            layer.attention.self = FusedSelfAttention(layer.attention.self)
        self.model.eval()
        head = mx.load(str(path / "sparse_linear.safetensors"))
        weight, bias = head.get("weight"), head.get("bias")
        if weight is None or bias is None:
            raise ValueError("Local sparse head is invalid.")
        weight, bias = weight.astype(mx.float32), bias.astype(mx.float32)
        if weight.shape != (1, 1024) or bias.shape not in ((1,), ()):
            raise ValueError("Local sparse head is invalid.")
        self.sparse_weight, self.sparse_bias = weight, bias
        self.special_ids = set(self.tokenizer.all_special_ids)
        pad_token_id = self.tokenizer.pad_token_id
        if pad_token_id is None:
            raise ValueError("Tokenizer padding token is required.")
        self.pad_token_id = int(pad_token_id)
        mx.eval(self.sparse_weight, self.sparse_bias)

    def tokenize(self, texts: list[str]) -> list[list[int]]:
        encoded = self.tokenizer(texts, add_special_tokens=True, truncation=False,
                                 padding=False, return_attention_mask=False)
        return encoded["input_ids"]

    def embed(self, token_ids: list[list[int]],
              return_sparse: bool = False) -> list[Embedding]:
        results = [None] * len(token_ids)
        for group in batch_groups([len(ids) for ids in token_ids]):
            vectors, sparse_rows = self._forward([token_ids[index] for index in group],
                                                 return_sparse)
            for index, vector, sparse in zip(group, vectors, sparse_rows):
                results[index] = Embedding(vector.tolist(), sparse)
        return results

    def _forward(self, token_ids: list[list[int]], return_sparse: bool):
        batch = len(token_ids)
        length = max(map(len, token_ids))
        input_ids = np.full((batch, length), self.pad_token_id, dtype=np.int32)
        attention_mask = np.zeros((batch, length), dtype=np.int32)
        for row, ids in enumerate(token_ids):
            input_ids[row, :len(ids)] = ids
            attention_mask[row, :len(ids)] = 1

        output = self.model(mx.array(input_ids), attention_mask=mx.array(attention_mask))
        hidden = output.last_hidden_state
        cls = hidden[:, 0, :].astype(mx.float32)
        vectors = cls / mx.sqrt(mx.sum(cls * cls, axis=-1, keepdims=True))
        if return_sparse:
            logits = mx.maximum(
                (hidden.astype(mx.float32) @ self.sparse_weight.T
                 + self.sparse_bias).squeeze(-1), 0)
            mx.eval(vectors, logits)
            sparse_values = np.asarray(logits)
        else:
            mx.eval(vectors)
            sparse_values = None

        values = np.asarray(vectors)
        if (values.shape != (batch, 1024) or not np.isfinite(values).all()
                or np.any(np.abs(np.linalg.norm(values, axis=1) - 1) > 1e-5)):
            raise RuntimeError("Invalid embedding output.")
        sparse_rows = ([self._sparse(ids, sparse_values[row, :len(ids)])
                        for row, ids in enumerate(token_ids)]
                       if return_sparse else [None] * batch)
        return values, sparse_rows

    def _sparse(self, ids: list[int], weights: np.ndarray) -> list[list[int | float]]:
        if weights.shape != (len(ids),) or not np.isfinite(weights).all():
            raise RuntimeError("Invalid sparse output.")
        # Aggregate by token id (max weight) in first-occurrence order. Indices
        # stay unique; Milvus sorts the pairs itself when packing a row.
        weights_by_id: dict[int, float] = {}
        for token_id, weight in zip(ids, weights):
            if token_id in self.special_ids or weight <= 0:
                continue
            key = int(token_id)
            if float(weight) > weights_by_id.get(key, 0.0):
                weights_by_id[key] = float(weight)
        return [[key, weight] for key, weight in weights_by_id.items()]
