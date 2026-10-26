import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx
from bge_embedding.app import create_app
from bge_embedding.config import load_config

CASES = {
    '20x1x25': {'requests': 20, 'texts': 1, 'length': 25},
    '16x4x25': {'requests': 16, 'texts': 4, 'length': 25},
}


def text_for(tag, request, index, length):
    # Unique payload per item; exact token count is checked by the app limits.
    base = f'{tag}-{request}-{index}-'
    return (base + 'x' * length)[:length]


async def run_case(client, key, name, spec, repeat):
    payloads = []
    for request in range(spec['requests']):
        texts = [text_for(f'{name}-{repeat}', request, index, spec['length'])
                 for index in range(spec['texts'])]
        payloads.append({'model': 'bge-m3', 'input': texts})
    async def one(body):
        started = time.perf_counter()
        response = await client.post('/v1/embeddings', headers={'Authorization': f'Bearer {key}'}, json=body)
        return response.status_code, time.perf_counter() - started, len(body['input'])
    started = time.perf_counter()
    results = await asyncio.gather(*(one(body) for body in payloads))
    wall = time.perf_counter() - started
    latencies = sorted(item[1] for item in results)
    statuses = sorted(set(item[0] for item in results))
    return {
        'requests': spec['requests'], 'texts_per_request': spec['texts'],
        'text_length': spec['length'], 'statuses': statuses, 'wall_s': round(wall, 4),
        'p50_ms': round(statistics.median(latencies) * 1000, 1),
        'p95_ms': round(latencies[max(0, int(len(latencies) * 0.95) - 1)] * 1000, 1),
        'max_ms': round(max(latencies) * 1000, 1),
        'latencies_ms': [round(x * 1000, 1) for x in latencies],
    }


async def main(tag, config_path, repeats):
    config = load_config(config_path)
    app = create_app(config)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://bench') as client:
            # Warm the model and tokenizer before measurements.
            await client.post('/v1/embeddings', headers={'Authorization': f'Bearer {config.auth.api_key}'},
                              json={'model': 'bge-m3', 'input': ['warmup']})
            rows = {}
            for repeat in range(repeats):
                for name, spec in CASES.items():
                    row = await run_case(client, config.auth.api_key, name, spec, repeat)
                    rows.setdefault(name, []).append(row)
                    print(name, repeat, row['statuses'], f"wall={row['wall_s']}s p50={row['p50_ms']}ms p95={row['p95_ms']}ms", flush=True)
    payload = {'tag': tag, 'git': __import__('subprocess').check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'cases': {name: {'spec': CASES[name], 'runs': values} for name, values in rows.items()}}
    Path(f'.cache/opt/p4_{tag}.json').write_text(json.dumps(payload, indent=2))
    print('WROTE', f'.cache/opt/p4_{tag}.json', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--config', default='config.toml')
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    asyncio.run(main(args.tag, args.config, args.repeats))
