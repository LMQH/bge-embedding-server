"""Bounded real-HTTP service measurements; never loads a second model."""
import argparse
import asyncio
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import plistlib
import re
import subprocess
import time
import uuid

import httpx


def percentile(values, quantile):
    values = sorted(values)
    return values[max(0, math.ceil(len(values) * quantile) - 1)] if values else None


def summarize(rows, wall):
    good = [r for r in rows if r['status'] == 200 and r['valid']]
    return {'requests': len(rows), 'success': len(good),
            'statuses': dict(Counter(str(r['status']) for r in rows)),
            'codes': dict(Counter(r['code'] for r in rows if r['code'])),
            'invalid': sum(r['status'] == 200 and not r['valid'] for r in rows),
            'wall_s': wall, 'tokens': sum(r['tokens'] for r in good),
            'tokens_s': sum(r['tokens'] for r in good) / wall,
            'texts_s': sum(r['texts'] for r in good) / wall,
            'p50_ms': percentile([r['latency_ms'] for r in good], .50),
            'p95_ms': percentile([r['latency_ms'] for r in good], .95),
            'scheduled_p95_ms': percentile([r['scheduled_ms'] for r in good], .95),
            'dispatch_p95_ms': percentile([r['dispatch_ms'] for r in rows], .95)}


def validate(data, batch, expected, sparse):
    try:
        items = data['data']
        assert len(items) == batch
        assert data['usage']['prompt_tokens'] == data['usage']['total_tokens'] == expected
        for index, item in enumerate(items):
            assert item['index'] == index
            v = item['embedding']
            assert len(v) == 1024 and all(math.isfinite(x) for x in v)
            assert abs(sum(x*x for x in v) - 1) < 2e-5
            if sparse:
                pairs = item['sparse']
                assert len({k for k, _ in pairs}) == len(pairs)
                assert all(type(k) is int and 0 <= k < 2**32-1
                           and math.isfinite(w) and w > 0 for k, w in pairs)
            else:
                assert 'sparse' not in item
        return True
    except (KeyError, TypeError, ValueError, AssertionError):
        return False


class Corpus:
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
        self.tag = uuid.uuid4().hex[:8]
        self.index = 0

    def text(self, length):
        self.index += 1
        prefix = f'算力{self.tag}{self.index:09d} '
        n = len(self.tokenizer.encode(prefix))
        text = prefix + 'test ' * (length - n)
        ids = self.tokenizer.encode(text)
        # The trailing space before test can change one boundary token.
        if len(ids) != length:
            text = self.tokenizer.decode(ids[1:length-1], skip_special_tokens=True)
            ids = self.tokenizer.encode(text)
        if len(ids) != length:
            raise ValueError('Cannot construct exact token length')
        return text

    def payload(self, length, batch, sparse):
        texts = [self.text(length) for _ in range(batch)]
        return {'model': 'bge-m3', 'input': texts, 'return_sparse': sparse}


async def request(client, body, expected, due, origin):
    start = time.monotonic()
    row = {'status': 'transport_error', 'code': '', 'valid': False, 'tokens': 0,
           'texts': len(body['input']), 'sparse': body['return_sparse'],
           'length': expected // len(body['input']), 'start_s': start-origin,
           'dispatch_ms': max(0, (start-due)*1000), 'retry_after': None}
    try:
        response = await client.post('/v1/embeddings', json=body)
        row['status'] = response.status_code
        row['retry_after'] = response.headers.get('Retry-After')
        data = response.json()
        if response.status_code == 200:
            row['valid'] = validate(data, len(body['input']), expected, body['return_sparse'])
            row['tokens'] = expected if row['valid'] else 0
        else:
            row['code'] = data.get('error', {}).get('code', 'unknown_error')
    except (httpx.HTTPError, ValueError) as exc:
        row['code'] = type(exc).__name__
    finish = time.monotonic()
    row.update(end_s=finish-origin, latency_ms=(finish-start)*1000,
               scheduled_ms=(finish-due)*1000)
    return row


async def arrivals(client, payloads, rate, duration, max_pending=64, on_row=None):
    origin = time.monotonic()
    pending, rows = set(), []
    scheduled = dropped = 0

    async def one(body, tokens, due):
        row = await request(client, body, tokens, due, origin)
        rows.append(row)
        if on_row:
            on_row(row)

    for index, (body, tokens) in enumerate(payloads):
        offset = index/rate
        if offset >= duration:
            break
        due = origin+offset
        await asyncio.sleep(max(0, due-time.monotonic()))
        pending = {t for t in pending if not t.done()}
        scheduled += 1
        if len(pending) >= max_pending:
            dropped += 1
            continue
        pending.add(asyncio.create_task(one(body, tokens, due)))
    await asyncio.sleep(max(0, origin+duration-time.monotonic()))
    if pending:
        await asyncio.gather(*pending)
    wall = time.monotonic()-origin
    result = summarize(rows, wall)
    result.update(scheduled=scheduled, dropped=dropped, arrival_window_s=duration,
                  drain_s=max(0, wall-duration), offered_rps=rate)
    return rows, result


def pid():
    result = subprocess.run(['launchctl', 'list', 'local.bge-embedding'],
                            capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if '"PID"' in line:
            return int(line.split('=')[1].strip(' ;'))
    return None


async def sample_resources(path, stop):
    with path.open('w') as out:
        while not stop.is_set():
            service_pid = pid()
            row = {'time': time.time(), 'pid': service_pid}
            if service_pid:
                r = await asyncio.create_subprocess_exec(
                    'ps', '-o', 'rss=,%cpu=', '-p', str(service_pid),
                    stdout=asyncio.subprocess.PIPE)
                raw = (await r.communicate())[0].decode().split()
                if len(raw) == 2:
                    row.update(rss_kib=int(raw[0]), cpu_percent=float(raw[1]))
            for name, command in [('swap', ['sysctl', '-n', 'vm.swapusage']),
                                  ('vm', ['vm_stat'])]:
                r = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE)
                raw = (await r.communicate())[0].decode()
                if name == 'swap':
                    row[name] = raw.strip()
                else:
                    row['vm'] = {line.split(':')[0].strip(): line.split(':')[1].strip(' .\n')
                                 for line in raw.splitlines() if ':' in line}
            out.write(json.dumps(row)+'\n'); out.flush()
            try:
                await asyncio.wait_for(stop.wait(), 2)
            except TimeoutError:
                pass


async def sample_logs(log_path, destination, stop):
    process = await asyncio.create_subprocess_exec(
        'tail', '-n', '0', '-F', log_path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        with destination.open('w') as out:
            while not stop.is_set():
                try:
                    raw = await asyncio.wait_for(process.stdout.readline(), 1)
                except TimeoutError:
                    continue
                line = raw.decode(errors='replace')
                if 'path=/v1/embeddings ' in line:
                    fields = dict(re.findall(r'(status|tokens|hits|wait_ms|exec_ms|ahead|dedup)=(\d+)', line))
                    if fields:
                        out.write(json.dumps({'time': time.time(), **{k: int(v) for k,v in fields.items()}})+'\n')
                        out.flush()
    finally:
        process.terminate()
        await process.wait()


def config_path(args):
    if args.config:
        return Path(args.config)
    d = plistlib.loads((Path.home()/'Library/LaunchAgents/local.bge-embedding.plist').read_bytes())
    a = d['ProgramArguments']
    return Path(a[a.index('--config')+1])


async def main(args):
    from bge_embedding.config import load_config
    from transformers import AutoTokenizer
    config = load_config(config_path(args))
    tokenizer = AutoTokenizer.from_pretrained(config.model.path, local_files_only=True)
    corpus = Corpus(tokenizer)
    host = config.server.host
    if host in {'0.0.0.0', '::'}:
        host = '127.0.0.1' if host == '0.0.0.0' else '::1'
    if ':' in host:
        host = f'[{host}]'
    # If only a specific network interface is bound, a loopback URL is not assumed.
    base = f'http://{host}:{config.server.port}'
    args.output.mkdir(parents=True, exist_ok=True)
    stop = asyncio.Event()
    sampler = asyncio.create_task(sample_resources(args.output/'resources.jsonl', stop))
    log_sampler = asyncio.create_task(sample_logs(config.logging.file, args.output/'requestlogs.jsonl', stop))
    results = {}
    manifest = {'client_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'seed_tag': corpus.tag, 'started_at': time.time(),
                'queue': vars(config.queue), 'limits': vars(config.limits),
                'cache': vars(config.cache), 'mlx': vars(config.mlx),
                'transport': 'same-host-configured-bind', 'profile': args.profile,
                'model_config_sha256': hashlib.sha256((Path(config.model.path)/'config.json').read_bytes()).hexdigest()}
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2))

    def save(name, rows, summary):
        (args.output/f'{name}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        results[name] = summary
        (args.output/'summary.json').write_text(json.dumps(results, indent=2))
        print(json.dumps({'phase': name, **summary}), flush=True)

    async with httpx.AsyncClient(base_url=base, headers={'Authorization': 'Bearer '+config.auth.api_key},
                                timeout=120, trust_env=False,
                                limits=httpx.Limits(max_connections=64, max_keepalive_connections=64)) as client:
        try:
            assert (await client.get('/healthz')).json()['status'] == 'ready'
            if args.profile == 'baseline':
                for sparse in [False, True]:
                    for length, batch, count in [(32,1,100),(512,1,100),(2048,1,100),(512,16,20),(8192,1,3)]:
                        bodies = [corpus.payload(length,batch,sparse) for _ in range(count+3)]
                        for body in bodies[:3]:
                            r=await request(client,body,length*batch,time.monotonic(),time.monotonic())
                            assert r['valid'], r['status']
                        rows=[]; origin=time.monotonic()
                        for body in bodies[3:]:
                            rows.append(await request(client,body,length*batch,time.monotonic(),origin))
                        save(f'{"dual" if sparse else "dense"}-{batch}x{length}',rows,summarize(rows,time.monotonic()-origin))
                    body=corpus.payload(512,1,sparse)
                    await request(client,body,512,time.monotonic(),time.monotonic())
                    rows=[]; origin=time.monotonic()
                    for _ in range(100):
                        rows.append(await request(client,body,512,time.monotonic(),origin))
                    save(f'cache-{sparse}',rows,summarize(rows,time.monotonic()-origin))
            elif args.profile in {'short','mixed'}:
                count=math.ceil(args.rate*args.duration)
                bodies=[]
                for i in range(count):
                    length,batch=(32,1)
                    if args.profile=='mixed':
                        slot=i%20
                        length,batch=(512,16) if slot in (0,7,14) else ((2048,1) if slot==19 else (32,1))
                    # Each 20-request block has half dense and half dual, including short traffic.
                    sparse=(i//20)%2==1
                    bodies.append((corpus.payload(length,batch,sparse),length*batch))
                print(json.dumps({'prepared':len(bodies),'duration_s':args.duration,'rate':args.rate}),flush=True)
                with (args.output/'live.jsonl').open('w') as out:
                    def record(r):
                        out.write(json.dumps(r)+'\n');out.flush()
                    rows,result=await arrivals(client,bodies,args.rate,args.duration,on_row=record)
                for sparse in [False,True]:
                    for length in [32,512,2048]:
                        selected=[r for r in rows if r['sparse']==sparse and r['length']==length]
                        if selected:
                            result[f'{sparse}-{length}']=summarize(selected,result['wall_s'])
                save(args.profile,rows,result)
            elif args.profile=='overload':
                bodies=[corpus.payload(8192,4,False) for _ in range(24)]
                origin=time.monotonic()
                rows=await asyncio.gather(*(request(client,b,32768,origin,origin) for b in bodies))
                save('long-burst',rows,summarize(rows,time.monotonic()-origin))
                # Cancel one waiting and one active HTTP request; wait for non-interruptible GPU work.
                for delay in [.05, 1.0]:
                    body=corpus.payload(8192,4,False)
                    task=asyncio.create_task(client.post('/v1/embeddings',json=body))
                    await asyncio.sleep(delay); task.cancel()
                    try: await task
                    except asyncio.CancelledError: pass
                    await asyncio.sleep(20)
                rows=[];origin=time.monotonic()
                for _ in range(20):
                    b=corpus.payload(32,1,False)
                    rows.append(await request(client,b,32,time.monotonic(),origin))
                save('post-overload',rows,summarize(rows,time.monotonic()-origin))
        finally:
            stop.set();await sampler;await log_sampler
    (args.output/'complete.json').write_text(json.dumps({'completed_at':time.time()}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--config');source.add_argument('--launchd',action='store_true')
    p.add_argument('--profile',choices=['baseline','short','mixed','overload'],required=True)
    p.add_argument('--rate',type=float,default=1)
    p.add_argument('--duration',type=float,default=300)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.rate<=0 or a.duration<=0:p.error('rate and duration must be positive')
    asyncio.run(main(a))
