"""Explicit maintenance-window checks for queue abandonment and launchd recovery."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
import sys
import time

import httpx

from service_load import Corpus, config_path, pid, request, summarize


async def ready(client, old_pid):
    started=time.monotonic()
    while time.monotonic()-started < 120:
        current=pid()
        if current and current != old_pid:
            try:
                response=await client.get('/healthz',timeout=2)
                if response.status_code==200 and response.json().get('status')=='ready':
                    return {'ready_seconds':time.monotonic()-started,'pid_changed':True}
            except httpx.HTTPError:
                pass
        await asyncio.sleep(.25)
    raise RuntimeError('Service did not recover within 120 seconds')


async def main(args):
    from bge_embedding.config import load_config
    from transformers import AutoTokenizer
    config=load_config(config_path(args))
    corpus=Corpus(AutoTokenizer.from_pretrained(config.model.path,local_files_only=True))
    host=config.server.host
    if host=='0.0.0.0':host='127.0.0.1'
    if host=='::':host='::1'
    if ':' in host:host=f'[{host}]'
    base=f'http://{host}:{config.server.port}'
    args.output.mkdir(parents=True,exist_ok=True)
    result={}
    async with httpx.AsyncClient(base_url=base,headers={'Authorization':'Bearer '+config.auth.api_key},
                                timeout=120,trust_env=False) as client:
        async def health_and_probe():
            body=corpus.payload(32,1,False)
            row=await request(client,body,32,time.monotonic(),time.monotonic())
            assert row['valid'],row
            return row

        # Ensure the canceled request was waiting behind a genuine GPU workload.
        origin=time.monotonic()
        active=asyncio.create_task(request(client,corpus.payload(8192,4,False),32768,origin,origin))
        await asyncio.sleep(.3)
        waiting=asyncio.create_task(client.post('/v1/embeddings',json=corpus.payload(32,1,False)))
        await asyncio.sleep(.2);waiting.cancel()
        try:await waiting
        except asyncio.CancelledError:pass
        active_result=await active
        result['waiting_cancel']={'active':active_result,'probe':await health_and_probe()}
        print('waiting cancellation checked',flush=True)

        # Graceful termination during one active and two waiting long requests.
        old=pid()
        assert old and old!=os.getpid()
        origin=time.monotonic()
        bodies=[corpus.payload(8192,4,False) for _ in range(3)]
        tasks=[asyncio.create_task(request(client,bodies[0],32768,origin,origin))]
        await asyncio.sleep(.3)
        tasks.extend(asyncio.create_task(request(client,b,32768,time.monotonic(),origin)) for b in bodies[1:])
        await asyncio.sleep(.3)
        signaled=time.monotonic();os.kill(old,signal.SIGTERM)
        responses=await asyncio.gather(*tasks)
        restored=await ready(client,old)
        restored['signal_to_ready_seconds']=time.monotonic()-signaled
        result['sigterm']={'requests':responses,'recovery':restored,
                           'waiting_503_observed':any(r['status']==503 for r in responses[1:]),
                           'probe':await health_and_probe()}
        (args.output/'recovery.json').write_text(json.dumps(result,indent=2))
        print('SIGTERM recovery',json.dumps(restored),flush=True)

        # Abnormal process exit; launchd must start a different process.
        old=pid();assert old and old!=os.getpid()
        signaled=time.monotonic();os.kill(old,signal.SIGKILL)
        restored=await ready(client,old)
        restored['signal_to_ready_seconds']=time.monotonic()-signaled
        result['sigkill']={'recovery':restored,'probe':await health_and_probe()}
        (args.output/'recovery.json').write_text(json.dumps(result,indent=2))
        print('SIGKILL recovery',json.dumps(restored),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launchd',action='store_true',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.config=None
    asyncio.run(main(a))
