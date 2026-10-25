from uuid import uuid4
from datetime import UTC,datetime
import httpx
import pytest
from conftest import account,drain
from offerpilot.infrastructure.config import settings
from offerpilot.modules.runs.service import provider_ready
from offerpilot.api.errors import DomainError
from offerpilot.providers.base import ProviderError,SearchResult
from offerpilot.providers.fixtures import FixtureProvider


@pytest.mark.parametrize('mode,expected',[('partial','partial'),('failed','failed'),('zero','succeeded')])
async def test_search_failures_and_zero(client:httpx.AsyncClient,monkeypatch,mode,expected):
    await account(client)
    original=FixtureProvider.search
    count=0
    async def search(self,query,max_results=8):
        nonlocal count
        count+=1
        if mode=='failed' or mode=='partial' and count==1:raise ProviderError('synthetic_failure')
        if mode=='zero':return SearchResult(results=[])
        return await original(self,query,max_results)
    monkeypatch.setattr(FixtureProvider,'search',search)
    spec=(await client.post('/api/v1/search-specs',json={'keywords':'Python','confirmed':True})).json()
    r=await client.post('/api/v1/search-runs',json={'spec_id':spec['id']},headers={'Idempotency-Key':str(uuid4())})
    await drain()
    run=(await client.get('/api/v1/runs/'+r.json()['id'])).json()
    assert run['status']==expected,run
    if mode=='zero':assert run['result']['counts']['raw_links']==0


async def test_job_versions_same_url_and_duplicates_undo(client:httpx.AsyncClient):
    await account(client)
    ids=[]
    for text,url in [('合成Python岗位\n每周至少3天','https://example.com/job?id=2'),('合成Python岗位\n每周至少4天','https://example.com/job?id=2'),('合成Python岗位\n每周至少4天','https://other.example/job?id=2')]:
        r=await client.post('/api/v1/job-imports',json={'text':text,'url':url},headers={'Idempotency-Key':str(uuid4())})
        await drain()
        run=(await client.get('/api/v1/runs/'+r.json()['id'])).json()
        ids.append(run['result']['job_ids'][0])
    assert ids[0]==ids[1] and ids[1]!=ids[2]
    assert len((await client.get('/api/v1/jobs/'+ids[0])).json()['versions'])==2
    pairs=(await client.get('/api/v1/duplicate-reviews')).json()['items']
    assert len(pairs)==1
    pair=pairs[0]
    merged=await client.post('/api/v1/duplicate-reviews/'+pair['id']+'/decision',json={'expected_revision':pair['revision'],'decision':'merge','reason':'本人核对来源一致'})
    assert merged.status_code==200,merged.text
    event=(await client.get('/api/v1/job-merges')).json()['items'][0]
    assert (await client.post('/api/v1/job-merges/'+event['id']+'/undo')).json()['undone']
    assert len((await client.get('/api/v1/jobs')).json()['items'])==2


async def test_idempotency_payload_conflict_and_cancel(client:httpx.AsyncClient):
    await account(client)
    k=str(uuid4())
    r=await client.post('/api/v1/job-imports',json={'text':'合成A'},headers={'Idempotency-Key':k})
    assert (await client.post('/api/v1/job-imports',json={'text':'合成B'},headers={'Idempotency-Key':k})).status_code==409
    await client.post('/api/v1/runs/'+r.json()['id']+'/cancel')
    await drain()
    assert (await client.get('/api/v1/runs/'+r.json()['id'])).json()['status']=='cancelled'


def test_live_never_uses_fixtures(monkeypatch):
    cfg=settings()
    monkeypatch.setattr(cfg,'app_mode','live')
    from pydantic import SecretStr
    monkeypatch.setattr(cfg,'deepseek_api_key',SecretStr(''))
    monkeypatch.setattr(cfg,'tavily_api_key',SecretStr(''))
    with pytest.raises(DomainError,match='尚未配置'):provider_ready('search')


async def test_same_board_without_external_id_keeps_distinct_jobs(client:httpx.AsyncClient):
    await account(client)
    ids=[]
    for i,city in enumerate(['杭州','上海','北京']):
        r=await client.post('/api/v1/job-imports',json={'text':f'合成同标题岗位\n城市：{city}\n要求Python','url':f'https://same-board.example/jobs/{i}'},headers={'Idempotency-Key':str(uuid4())})
        await drain()
        result=(await client.get('/api/v1/runs/'+r.json()['id'])).json()
        ids.append(result['result']['job_ids'][0])
    assert len(set(ids))==3


async def test_supported_source_id_keeps_url_aliases(client:httpx.AsyncClient):
    from uuid import UUID
    from offerpilot.infrastructure.db import Session
    from offerpilot.infrastructure.owned import lock_owner
    from offerpilot.modules.jobs.schemas import JobExtraction,FieldProvenance
    from offerpilot.modules.jobs.service import save_extraction
    owner=UUID(await account(client))
    text='合成岗位\n职位编号：source-7'
    data=JobExtraction(classification='job_detail',title='合成岗位',company='合成',source_job_id='source-7',field_evidence={'source_job_id':FieldProvenance(value='source-7',source_kind='user_provided',paragraph_id='p2',quote='职位编号：source-7')})
    async with Session() as db:
        await lock_owner(db,owner)
        job,_=await save_extraction(db,owner,data,text,'https://aliases.example/a','user_provided');await db.commit()
        await lock_owner(db,owner)
        again,_=await save_extraction(db,owner,data,text,'https://aliases.example/b','user_provided');await db.commit()
        assert job.id==again.id
    result=(await client.get('/api/v1/jobs/'+str(job.id))).json()
    assert result['sources'][0]['aliases']==['https://aliases.example/b']
