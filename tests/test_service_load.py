"""Check load accounting independently of real model performance."""
import asyncio
import importlib.util
from pathlib import Path

import httpx
import pytest

spec=importlib.util.spec_from_file_location('service_load',Path(__file__).parent/'benchmarks/service_load.py')
load=importlib.util.module_from_spec(spec)
spec.loader.exec_module(load)


def test_success_throughput_excludes_rejection_and_bad_output():
    rows=[dict(status=s,valid=v,tokens=t,texts=1,code=c,latency_ms=10,
               scheduled_ms=12,dispatch_ms=2) for s,v,t,c in
          [(200,True,512,''),(429,False,0,'queue_full'),(200,False,0,'')]]
    result=load.summarize(rows,2)
    assert result['tokens_s']==256
    assert result['success']==1 and result['requests']==3 and result['invalid']==1
    assert result['codes']=={'queue_full':1}


@pytest.mark.asyncio
async def test_slow_server_does_not_silently_reduce_offered_load():
    async def slow(request):
        await asyncio.sleep(.08)
        return httpx.Response(429,json={'error':{'code':'queue_full'}},headers={'Retry-After':'1'})
    body={'input':['x'],'return_sparse':False}
    async with httpx.AsyncClient(base_url='http://test',transport=httpx.MockTransport(slow)) as client:
        rows,result=await load.arrivals(client,[(body,3)]*20,100,.2,max_pending=1)
    assert result['scheduled']==20
    assert result['dropped']>0
    assert len(rows)+result['dropped']==20
    assert all(r['retry_after']=='1' for r in rows)
    assert result['success']==0


@pytest.mark.asyncio
async def test_transport_timeout_is_counted():
    async def timeout(request):
        raise httpx.ReadTimeout('test')
    async with httpx.AsyncClient(base_url='http://test',transport=httpx.MockTransport(timeout)) as client:
        row=await load.request(client,{'input':['x'],'return_sparse':False},3,0,0)
    assert row['status']=='transport_error' and row['code']=='ReadTimeout'
