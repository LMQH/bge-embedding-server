import json
import numpy as np

base = np.load('.cache/opt/baseline_quality.npz')
fp16 = np.load('.cache/opt/fp16_quality.npz')
a, b = base['dense'], fp16['dense']
lengths = base['lengths'].tolist()
cos = np.sum(a * b, axis=1)
print('lengths', lengths)
print('cosine', [round(float(x), 9) for x in cos])
print('min cosine', float(cos.min()))
print('max abs dense delta', float(np.abs(a - b).max()))
print('norms fp16', [round(float(x), 6) for x in np.linalg.norm(b, axis=1)])
sa = json.loads(open('.cache/opt/baseline_sparse.json').read())
sb = json.loads(open('.cache/opt/fp16_sparse.json').read())
for i, (x, y) in enumerate(zip(sa, sb)):
    assert set(x) == set(y), (i, set(x) ^ set(y))
    diffs = [abs(x[k] - y[k]) for k in x]
    rel = [abs(x[k] - y[k]) / max(abs(x[k]), 1e-12) for k in x]
    print(f'sparse[{i}] n={len(x)} max_abs={max(diffs) if diffs else 0:.3e} max_rel={max(rel) if rel else 0:.3e}')
