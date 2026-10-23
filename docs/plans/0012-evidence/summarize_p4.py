import json, statistics
for tag in ('baseline','final'):
    d=json.load(open(f'.cache/opt/p4_{tag}.json'))
    print(tag, d['git'])
    for name, case in d['cases'].items():
        runs=case['runs']
        p95=[r['p95_ms'] for r in runs]; wall=[r['wall_s'] for r in runs]; p50=[r['p50_ms'] for r in runs]
        print(name, 'runs', len(runs), 'p95 median', statistics.median(p95), 'range', min(p95), max(p95),
              'p50 median', statistics.median(p50), 'wall median', statistics.median(wall), 'range', min(wall), max(wall))
