import json
from uuid import UUID, uuid4
import httpx
from sqlalchemy import func,select
from conftest import account,drain
from offerpilot.infrastructure.db import Session
from offerpilot.infrastructure.config import settings
from offerpilot.modules.discovery.models import SearchCandidateAnalysis
from offerpilot.modules.identity.models import User
from offerpilot.providers.base import SearchResult,SearchHit
from offerpilot.providers.fixtures import FixtureProvider


async def scoped_search(client, natural=False):
    if natural:
        return await client.post('/api/v1/search-runs/natural',json={'text':'帮我找找杭州开发相关实习','max_queries':1,'public_info_ai_consent':True},headers={'Idempotency-Key':str(uuid4())})
    spec=(await client.post('/api/v1/search-specs',json={'keywords':'Python开发','cities':['杭州'],'max_queries':1,'confirmed':True})).json()
    return await client.post('/api/v1/search-runs',json={'spec_id':spec['id'],'public_info_ai_consent':True},headers={'Idempotency-Key':str(uuid4())})


async def test_public_search_no_resume_consent_and_no_private_context(client:httpx.AsyncClient,monkeypatch):
    await account(client)
    await client.post('/api/v1/me/model-consent',json={'granted':False})
    await client.post('/api/v1/resume-versions',json={'title':'合成私密','text':'private-resume-never-search-unique','parse':False},headers={'Idempotency-Key':str(uuid4())})
    captured=[];original=FixtureProvider.generate_json
    async def track(self,task,schema,inputs,max_tokens=4096):
        captured.append(json.dumps(inputs,ensure_ascii=False))
        return await original(self,task,schema,inputs,max_tokens)
    monkeypatch.setattr(FixtureProvider,'generate_json',track)
    response=await scoped_search(client,natural=True)
    assert response.status_code==202,response.text
    await drain()
    run=(await client.get('/api/v1/runs/'+response.json()['id'])).json()
    assert run['status']=='succeeded',run
    items=(await client.get('/api/v1/search-runs/'+run['id']+'/candidates')).json()['items']
    assert items[0]['intelligence']['opportunities']
    assert items[0]['intelligence']['opportunities'][0]['difficulty']['level']=='medium'
    assert not (await client.get('/api/v1/me/model-consent')).json()['granted']
    assert all('private-resume-never-search-unique' not in s for s in captured)


async def metadata_provider(monkeypatch, domain=None):
    domain=domain or f'cards-{uuid4().hex}.example'
    async def search(self,query,max_results=8):
        return SearchResult(results=[SearchHit(url=f'https://{domain}/jobs/1',title='合成星河科技 Python应用开发实习生',content='合成星河科技招聘Python应用开发实习生，杭州；本科及以上；Python、SQL；每周至少3天。')])
    async def forbidden(self,urls):raise AssertionError('metadata-only source must not be fetched')
    monkeypatch.setattr(FixtureProvider,'search',search);monkeypatch.setattr(FixtureProvider,'extract',forbidden)
    return domain


async def test_excerpt_cards_are_useful_without_fabricating_complete_jd(client:httpx.AsyncClient,monkeypatch):
    await account(client);await metadata_provider(monkeypatch)
    response=await scoped_search(client);await drain()
    candidate=(await client.get('/api/v1/search-runs/'+response.json()['id']+'/candidates')).json()['items'][0]
    assert candidate['status']=='metadata_only' and candidate['job_id'] is None
    intel=candidate['intelligence'];assert intel['basis']=='search_excerpt'
    assert intel['opportunities'][0]['company']=='合成星河科技'
    assert intel['opportunities'][0]['salary'] is None
    assert not (await client.get('/api/v1/jobs')).json()['items']


async def test_reorganize_is_versioned_idempotent_and_owned(client:httpx.AsyncClient):
    owner=UUID(await account(client));response=await scoped_search(client);await drain()
    source=response.json()['id'];headers={'Idempotency-Key':str(uuid4())}
    first=await client.post('/api/v1/search-runs/'+source+'/organize',json={'public_info_ai_consent':True},headers=headers)
    repeated=await client.post('/api/v1/search-runs/'+source+'/organize',json={'public_info_ai_consent':True},headers=headers)
    assert first.status_code==202 and first.json()['id']==repeated.json()['id']
    await drain()
    completed=(await client.get('/api/v1/runs/'+first.json()['id'])).json()
    repeated_after_completion=await client.post('/api/v1/search-runs/'+source+'/organize',json={'public_info_ai_consent':True},headers=headers)
    assert repeated_after_completion.json()['result']==completed['result']
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(SearchCandidateAnalysis).where(SearchCandidateAnalysis.owner_id==owner))==2
    await account(client)
    assert (await client.post('/api/v1/search-runs/'+source+'/organize',json={'public_info_ai_consent':True},headers={'Idempotency-Key':str(uuid4())})).status_code==404
    assert (await client.get('/api/v1/search-runs/'+source+'/candidates')).status_code==404


async def test_source_restriction_clears_ai_derived_information(client:httpx.AsyncClient,monkeypatch):
    owner=UUID(await account(client));domain=await metadata_provider(monkeypatch)
    response=await scoped_search(client);await drain();source=response.json()['id']
    async with Session() as db:
        user=await db.get(User,owner);user.is_admin=True;await db.commit()
    p=await client.post('/api/v1/admin/source-policies',json={'domain':domain,'purpose':'jobs','mode':'metadata_only','store_excerpt':False,'usage_basis':'合成来源撤回片段存储许可'})
    assert p.status_code==201,p.text
    item=(await client.get('/api/v1/search-runs/'+source+'/candidates')).json()['items'][0]
    assert item['intelligence'] is None and not item['summary']
    await client.post('/api/v1/search-runs/'+source+'/organize',json={'public_info_ai_consent':True},headers={'Idempotency-Key':str(uuid4())});await drain()
    assert (await client.get('/api/v1/search-runs/'+source+'/candidates')).json()['items'][0]['intelligence'] is None


async def test_card_budget_failure_retains_retrieved_links(client:httpx.AsyncClient,monkeypatch):
    await account(client);await metadata_provider(monkeypatch)
    monkeypatch.setattr(settings(),'run_max_calls',1)
    response=await scoped_search(client);await drain()
    run=(await client.get('/api/v1/runs/'+response.json()['id'])).json()
    assert run['status']=='partial' and run['error_code']=='budget_exhausted'
    assert (await client.get('/api/v1/search-runs/'+run['id']+'/candidates')).json()['items']


async def test_scoped_consent_does_not_authorize_private_resume_processing(client:httpx.AsyncClient):
    await account(client)
    await client.post('/api/v1/me/model-consent',json={'granted':False})
    response=await client.post('/api/v1/resume-versions',json={'title':'合成简历','text':'使用Python完成合成接口。'},headers={'Idempotency-Key':str(uuid4())})
    assert response.status_code in {403,409},response.text


async def test_restricted_source_excerpt_is_not_restored_by_new_search(client:httpx.AsyncClient,monkeypatch):
    owner=UUID(await account(client));domain=await metadata_provider(monkeypatch)
    async with Session() as db:
        user=await db.get(User,owner);user.is_admin=True;await db.commit()
    await client.post('/api/v1/admin/source-policies',json={'domain':domain,'purpose':'jobs','mode':'metadata_only','store_excerpt':False,'usage_basis':'合成来源禁止摘要留存'})
    response=await scoped_search(client);await drain()
    item=(await client.get('/api/v1/search-runs/'+response.json()['id']+'/candidates')).json()['items'][0]
    assert not item['summary'] and item['intelligence'] is None
