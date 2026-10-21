"""Manual, scoped diagnosis for the long-input memory bug; not a benchmark suite."""
import argparse
import json
from pathlib import Path
import re
import resource
import subprocess
import time

import mlx.core as mx
import numpy as np

from bge_embedding.inference import Embedder
from bge_embedding.config import load_config


def swap_snapshot():
    usage = subprocess.check_output(['sysctl', '-n', 'vm.swapusage'], text=True).strip()
    stats = subprocess.check_output(['vm_stat'], text=True)
    counters = {name: int(re.search(rf'^{name}:\s+(\d+)', stats, re.M)[1])
                for name in ('Swapins', 'Swapouts')}
    return {'usage': usage, **counters}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--lengths', nargs='+', type=int, default=[512, 2048])
    parser.add_argument('--compare')
    args = parser.parse_args()
    config = load_config(args.config)
    model = Embedder(config.model.path, config.mlx)
    texts = ['知识库检索与 English text.', '  保留首尾空白。  ']
    texts += ['test ' * (n - 2) for n in args.lengths]
    tokens = model.tokenize(texts)
    assert [len(ids) for ids in tokens[2:]] == args.lengths
    vectors, results = [], []
    for ids in tokens:
        mx.clear_cache()
        mx.reset_peak_memory()
        before = swap_snapshot()
        started = time.monotonic()
        vector = model.embed([ids])[0].dense
        elapsed = time.monotonic() - started
        after = swap_snapshot()
        vectors.append(vector)
        row = dict(tokens=len(ids), seconds=elapsed, active=mx.get_active_memory(),
                   cache=mx.get_cache_memory(), peak=mx.get_peak_memory(),
                   rss_peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   swap_before=before, swap_after=after)
        assert len(vector) == 1024 and np.isfinite(vector).all()
        assert abs(float(np.linalg.norm(vector)) - 1) < 1e-5
        results.append(row)
        print(json.dumps(row), flush=True)
    if args.compare:
        baseline = np.load(args.compare)['vectors']
        current = np.asarray(vectors[:len(baseline)])
        similarity = np.sum(current * baseline, axis=1) / (np.linalg.norm(current, axis=1) * np.linalg.norm(baseline, axis=1))
        print('cosine', similarity.tolist(), flush=True)
        assert np.all(similarity >= 0.9999), similarity
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix('.json').write_text(json.dumps(results, indent=2) + '\n')
    np.savez(path.with_suffix('.npz'), vectors=np.asarray(vectors))


if __name__ == '__main__':
    main()
