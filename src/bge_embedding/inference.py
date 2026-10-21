"""Local-only MLX loading and explicit raw CLS pooling."""
from dataclasses import dataclass
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np


@dataclass
class Embedding:
    dense: list[float]
    sparse: dict[str, float] | None = None


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
            return projected.transpose(0, 2, 1, 3).astype(mx.float32)

        # Additive padding mask, never causal: BGE uses bidirectional attention.
        context = mx.fast.scaled_dot_product_attention(
            project(self.query), project(self.key), project(self.value),
            scale=self.head_dim ** -0.5, mask=attention_mask, force_fused=True)
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
        mx.eval(self.sparse_weight, self.sparse_bias)

    def tokenize(self, texts: list[str]) -> list[list[int]]:
        encoded = self.tokenizer(texts, add_special_tokens=True, truncation=False,
                                 padding=False, return_attention_mask=False)
        return encoded["input_ids"]

    def embed(self, token_ids: list[list[int]],
              return_sparse: bool = False) -> list[Embedding]:
        results = []
        for ids in token_ids:
            inputs = mx.array([ids])
            output = self.model(inputs, attention_mask=mx.ones(inputs.shape, dtype=mx.int32))
            hidden = output.last_hidden_state
            cls = hidden[:, 0, :].astype(mx.float32)
            vector = cls / mx.sqrt(mx.sum(cls * cls, axis=-1, keepdims=True))
            if return_sparse:
                logits = mx.maximum(
                    (hidden.astype(mx.float32) @ self.sparse_weight.T
                     + self.sparse_bias).squeeze(-1), 0)
                mx.eval(vector, logits)
                sparse = self._sparse(ids, np.asarray(logits)[0])
            else:
                mx.eval(vector)
                sparse = None
            values = np.asarray(vector)[0]
            if (values.shape != (1024,) or not np.isfinite(values).all()
                    or abs(float(np.linalg.norm(values)) - 1) > 1e-5):
                raise RuntimeError("Invalid embedding output.")
            results.append(Embedding(values.tolist(), sparse))
        return results

    def _sparse(self, ids: list[int], weights: np.ndarray) -> dict[str, float]:
        if weights.shape != (len(ids),) or not np.isfinite(weights).all():
            raise RuntimeError("Invalid sparse output.")
        sparse = {}
        for token_id, weight in zip(ids, weights):
            if token_id in self.special_ids or weight <= 0:
                continue
            key = str(int(token_id))
            if float(weight) > sparse.get(key, 0.0):
                sparse[key] = float(weight)
        return sparse
