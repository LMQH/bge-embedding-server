"""Baseline/A-B harness for attention optimizations (scratch, not committed)."""
import argparse
import json
import statistics
import time
from pathlib import Path

import numpy as np
import mlx.core as mx

import bge_embedding.inference as inference
from bge_embedding.config import load_config
from bge_embedding.inference import Embedder

ROOT = Path('.cache/opt')
QUALITY_LENGTHS = [25, 64, 256, 512, 1024, 25, 128]
BENCH_CASES = {
    '16x25': [25] * 16,
    '16x256': [256] * 16,
    '16x512': [512] * 16,
    '16x1024': [1024] * 16,
    '4x8192': [8192] * 4,
    'mixed': [25, 64, 256, 512, 1024, 25, 128, 2048,
              25, 256, 512, 1024, 64, 128, 256, 512],
}
REPEATS = {'16x25': 3, '16x256': 3, '16x512': 3, '16x1024': 2,
           '4x8192': 1, 'mixed': 2}


def text_for(length):
    return 'test ' * (length - 2)


def load():
    config = load_config('config.toml')
    return Embedder(config.model.path, config.mlx)


def quality(model, tag):
    texts = [text_for(length) for length in QUALITY_LENGTHS]
    tokens = model.tokenize(texts)
    lengths = [len(ids) for ids in tokens]
    assert lengths == QUALITY_LENGTHS, lengths
    embeddings = model.embed(tokens, return_sparse=True)
    dense = np.stack([item.dense for item in embeddings])
    sparse = [item.sparse for item in embeddings]
    np.savez(ROOT / f'{tag}_quality.npz', dense=dense, lengths=np.array(lengths))
    (ROOT / f'{tag}_sparse.json').write_text(json.dumps(sparse, indent=2))
    print(f'QUALITY {tag} lengths={lengths} dense={dense.shape}', flush=True)


def bench(model, tag):
    rows = {}
    for name, lengths in BENCH_CASES.items():
        texts = [text_for(length) for length in lengths]
        tokens = model.tokenize(texts)
        assert [len(ids) for ids in tokens] == lengths, (name, [len(ids) for ids in tokens])
        model.embed(tokens)  # warmup
        durations, peaks = [], []
        for _ in range(REPEATS[name]):
            mx.clear_cache()
            mx.reset_peak_memory()
            started = time.perf_counter()
            model.embed(tokens)
            durations.append(time.perf_counter() - started)
            peaks.append(int(mx.get_peak_memory()))
        rows[name] = {'lengths': lengths, 'median_s': round(statistics.median(durations), 4),
                      'runs_s': [round(value, 4) for value in durations],
                      'peak_mib': round(max(peaks) / 2**20, 1), 'tokens': sum(lengths)}
        print(f'BENCH {tag} {name} {rows[name]}', flush=True)
    (ROOT / f'{tag}_bench.json').write_text(json.dumps(rows, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--eval-every', type=int, default=1)
    args = parser.parse_args()
    inference._ATTENTION_EVAL_EVERY = args.eval_every
    model = load()
    quality(model, args.tag)
    bench(model, args.tag)
    print(f'WROTE {args.tag}', flush=True)


if __name__ == '__main__':
    main()
