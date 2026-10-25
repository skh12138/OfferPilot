import asyncio
from datetime import timedelta
from uuid import UUID,uuid4
import httpx
import pytest
from sqlalchemy import select,func
from conftest import account,drain
from offerpilot.infrastructure.db import Session,now
from offerpilot.infrastructure.config import settings
from offerpilot.modules.runs.models import AgentRun,ProviderCall
from offerpilot.modules.runs.service import enqueue
from offerpilot.worker.queue import claim
from offerpilot.worker.context import Context
from offerpilot.providers.fixtures import FixtureProvider
from offerpilot.modules.jobs.schemas import JobExtraction


async def test_completed_step_reused_after_crash(client:httpx.AsyncClient):
    owner=UUID(await account(client))
    async with Session() as db:
        run=await enqueue(db,owner,'job_import',{'text':'合成恢复岗位\n要求 Python'},str(uuid4()))
    first=await claim('crashed-worker');assert first and first[0]==run.id
    ctx=Context(run,first[1]);provider=FixtureProvider()
    await ctx.generate('normalize:0','job_normalize',JobExtraction,{'text':'合成恢复岗位\n要求 Python'},provider.generate_json)
    async with Session() as db:
        row=await db.get(AgentRun,run.id);row.lease_expires_at=now()-timedelta(seconds=1);await db.commit()
    second=await claim('replacement-worker');assert second and second[1]!=first[1]
    from offerpilot.workflows.graphs import execute
    await execute(*second)
    async with Session() as db:
        calls=await db.scalar(select(func.count()).select_from(ProviderCall).where(ProviderCall.run_id==run.id))
        assert calls==1
    assert (await client.get('/api/v1/runs/'+str(run.id))).json()['status']=='succeeded'


async def test_semantic_repair_only_once_and_manual_path(client:httpx.AsyncClient,monkeypatch):
    from offerpilot.providers.base import Generated,Usage
    await account(client)
    app=(await client.post('/api/v1/applications',json={'title':'合成','company':'合成'},headers={'Idempotency-Key':str(uuid4())})).json()
    calls=0
    async def invalid(self,task,schema,inputs,max_tokens=4096):
        nonlocal calls
        calls+=1
        return Generated(data={},usage=Usage(input_tokens=1,output_tokens=1))
    monkeypatch.setattr(FixtureProvider,'generate_json',invalid)
    response=await client.post('/api/v1/applications/'+app['id']+'/preparation-runs',json={'expected_revision':app['revision']},headers={'Idempotency-Key':str(uuid4())})
    await drain()
    assert calls==2
    run=(await client.get('/api/v1/runs/'+response.json()['id'])).json()
    assert run['status']=='failed' and run['error_code']=='model_semantic_invalid'
    manual=await client.post('/api/v1/applications/'+app['id']+'/preparation-bundles',json={'expected_revision':app['revision'],'reason':'人工编辑','data':{'claims':[],'gaps':['到岗条件待核实'],'tasks':[],'introduction':'按背景、贡献、验证组织','contact_draft':'您好，请问到岗要求如何？'}})
    assert manual.status_code==201,manual.text


async def test_budget_exhaustion_retains_known_results(client:httpx.AsyncClient,monkeypatch):
    await account(client)
    monkeypatch.setattr(settings(),'run_max_calls',1)
    response=await client.post('/api/v1/job-imports',json={'text':'text,url\n"合成A\n要求Python",https://example.com/1\n"合成B\n要求Java",https://example.com/2','format':'csv'},headers={'Idempotency-Key':str(uuid4())})
    await drain()
    run=(await client.get('/api/v1/runs/'+response.json()['id'])).json()
    assert run['status']=='partial' and len(run['result']['job_ids'])==1,run
    assert run['result']['errors'][0]['code']=='budget_exhausted'


async def test_metadata_only_never_extracts(client:httpx.AsyncClient,monkeypatch):
    from offerpilot.providers.base import SearchResult,SearchHit
    await account(client)
    async def search(self,query,max_results=8):return SearchResult(results=[SearchHit(url='https://unknown.example/job',title='仅摘要合成线索',content='不能当正文')])
    async def forbidden(self,urls):raise AssertionError('metadata_only must never call extract')
    monkeypatch.setattr(FixtureProvider,'search',search);monkeypatch.setattr(FixtureProvider,'extract',forbidden)
    spec=(await client.post('/api/v1/search-specs',json={'keywords':'Python','confirmed':True})).json()
    run=await client.post('/api/v1/search-runs',json={'spec_id':spec['id']},headers={'Idempotency-Key':str(uuid4())})
    await drain()
    candidates=(await client.get('/api/v1/search-runs/'+run.json()['id']+'/candidates')).json()['items']
    assert candidates[0]['status']=='metadata_only' and candidates[0]['job_id'] is None
    assert not (await client.get('/api/v1/jobs')).json()['items']


async def test_cross_owner_run_sse_download_stats_and_links(client:httpx.AsyncClient):
    await account(client)
    run=await client.post('/api/v1/job-imports',json={'text':'合成隔离岗位\n要求 Python'},headers={'Idempotency-Key':str(uuid4())})
    await drain()
    first=(await client.get('/api/v1/runs/'+run.json()['id'])).json()
    job_id=first['result']['job_ids'][0]
    exported=(await client.post('/api/v1/me/exports',json={'format':'json'},headers={'Idempotency-Key':str(uuid4())})).json();await drain()
    await account(client)
    for path in ['/jobs/'+job_id,'/runs/'+first['id'],'/runs/'+first['id']+'/events','/me/exports/'+exported['id']+'/download']:
        assert (await client.get('/api/v1'+path)).status_code==404,path
    assert (await client.get('/api/v1/reports/overview')).json()['sample_size']==0
    response=await client.post('/api/v1/applications',json={'title':'跨用户','company':'错误关联','job_version_id':str(uuid4())},headers={'Idempotency-Key':str(uuid4())})
    assert response.status_code==404


async def test_admin_policy_report_and_no_private_entry(client:httpx.AsyncClient):
    owner=UUID(await account(client))
    from offerpilot.modules.identity.models import User
    async with Session() as db:
        user=await db.get(User,owner);user.is_admin=True;await db.commit()
    p=await client.post('/api/v1/admin/source-policies',json={'domain':f'{uuid4().hex}.example','mode':'metadata_only','purpose':'jobs','usage_basis':'合成契约，不表示真实来源获准'})
    assert p.status_code==201,p.text
    report=await client.post('/api/v1/feedback-reports',json={'target_kind':'other','message':'合成纠错','shared_excerpt':'仅主动分享文本','share_confirmed':True})
    row=report.json()
    resolved=await client.post('/api/v1/admin/feedback-reports/'+row['id']+'/resolution',json={'expected_revision':row['revision'],'status':'resolved','resolution':'合成复核已记录'})
    assert resolved.status_code==200,resolved.text
    overview=await client.get('/api/v1/admin/overview');assert overview.status_code==200
    assert 'resume' not in overview.text and 'password' not in overview.text
    assert (await client.get('/api/v1/admin/users/'+str(owner)+'/resume')).status_code==404
