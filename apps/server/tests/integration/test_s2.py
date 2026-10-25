from uuid import uuid4
from datetime import timedelta
import httpx
from sqlalchemy import select
from conftest import account,drain
from offerpilot.infrastructure.db import Session,now
from offerpilot.modules.runs.models import AgentRun,RunStatus,RunStep
from offerpilot.worker.queue import claim,guarded,LeaseLost


async def test_search_confirmation_and_sse(client:httpx.AsyncClient):
    await account(client)
    spec=(await client.post('/api/v1/search-specs',json={'keywords':'Python','cities':['杭州'],'days_per_week':3})).json()
    assert (await client.post('/api/v1/search-runs',json={'spec_id':spec['id']},headers={'Idempotency-Key':str(uuid4())})).status_code==409
    spec=(await client.post('/api/v1/search-specs',json={'keywords':'Python','cities':['杭州'],'days_per_week':3,'confirmed':True})).json()
    r=await client.post('/api/v1/search-runs',json={'spec_id':spec['id']},headers={'Idempotency-Key':str(uuid4())})
    assert r.status_code==202,r.text
    await drain()
    run=(await client.get('/api/v1/runs/'+r.json()['id'])).json()
    assert run['status']=='succeeded',run
    assert run['result']['counts']['raw_links']==2
    assert run['result']['counts']['new_jobs']==1
    candidates=(await client.get('/api/v1/search-runs/'+run['id']+'/candidates')).json()['items']
    assert len(candidates)==1 and candidates[0]['status']=='job_saved'
    events=await client.get('/api/v1/runs/'+run['id']+'/events')
    assert 'event: run_completed' in events.text
    seqs=[int(line[4:]) for line in events.text.splitlines() if line.startswith('id: ')]
    assert seqs==sorted(set(seqs))
    resumed=await client.get('/api/v1/runs/'+run['id']+'/events',headers={'Last-Event-ID':str(max(seqs))})
    assert not resumed.text


async def test_lease_fencing_and_capacity(client:httpx.AsyncClient):
    await account(client)
    r=await client.post('/api/v1/job-imports',json={'text':'合成岗位\n要求 Python'},headers={'Idempotency-Key':str(uuid4())})
    claimed=await claim('one')
    assert claimed is not None
    assert await claim('two') is None
    run_id,old_token=claimed
    async with Session() as db:
        run=await db.get(AgentRun,run_id)
        run.lease_expires_at=now()-timedelta(seconds=1)
        owner=run.owner_id
        await db.commit()
    second=await claim('two')
    assert second and second[0]==run_id and second[1]!=old_token
    async with Session() as db:
        import pytest
        with pytest.raises(LeaseLost): await guarded(db,owner,run_id,old_token)
    from offerpilot.workflows.graphs import execute
    await execute(*second)
    result=(await client.get('/api/v1/runs/'+r.json()['id'])).json()
    assert result['status']=='succeeded'
