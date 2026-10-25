import asyncio
from datetime import UTC,datetime,timedelta
from uuid import uuid4
import httpx
from sqlalchemy import select
from conftest import account,drain
from offerpilot.infrastructure.db import Session
from offerpilot.modules.identity.models import User
from offerpilot.providers.fixtures import FixtureProvider


async def base(client):
    r=await client.post('/api/v1/resume-versions',json={'title':'合成个人简历','text':'使用 Vue3 完成独有合成任务列表。'},headers={'Idempotency-Key':str(uuid4())})
    await drain()
    p=(await client.get('/api/v1/profiles/current')).json()['current']
    for f in p['facts']:f['status']='user_confirmed'
    p=(await client.post('/api/v1/profile-versions',json={k:p[k] for k in ['resume_version_id','preferences','facts']}|{'reason':'本人确认'})).json()
    app=(await client.post('/api/v1/applications',json={'title':'合成岗位','company':'合成企业','profile_version_id':p['id']},headers={'Idempotency-Key':str(uuid4())})).json()
    return p,app


async def test_offer_no_implicit_expiry_or_close(client:httpx.AsyncClient):
    await account(client)
    app=(await client.post('/api/v1/applications',json={'title':'合成A','company':'合成企业A'},headers={'Idempotency-Key':str(uuid4())})).json()
    other=(await client.post('/api/v1/applications',json={'title':'合成B','company':'合成企业B'},headers={'Idempotency-Key':str(uuid4())})).json()
    offer=await client.post('/api/v1/offers',json={'application_id':app['id'],'notification_confirmed':True,'type':'oral','source':'合成电话通知','salary_unit':'day','salary_raw':'200元/天','reply_deadline':'2020-01-01'})
    assert offer.status_code==201,offer.text
    row=offer.json()
    assert row['type']=='oral' and row['decision']=='undecided'
    accepted=await client.post('/api/v1/offers/'+row['id']+'/events',json={'expected_revision':row['revision'],'decision':'accepted','user_confirmed':True,'reason':'本人决定'},headers={'Idempotency-Key':str(uuid4())})
    assert accepted.status_code==200,accepted.text
    assert (await client.get('/api/v1/applications/'+app['id'])).json()['stage']=='onboarding'
    assert (await client.get('/api/v1/applications/'+other['id'])).json()['stage']=='interested'


async def test_delete_race_blocks_old_worker_and_exports(client:httpx.AsyncClient,monkeypatch):
    await account(client)
    profile,app=await base(client)
    r=await client.post('/api/v1/applications/'+app['id']+'/preparation-runs',json={'expected_revision':app['revision']},headers={'Idempotency-Key':str(uuid4())})
    started,release=asyncio.Event(),asyncio.Event()
    original=FixtureProvider.generate_json
    async def paused(self,task,schema,inputs,max_tokens=4096):
        result=await original(self,task,schema,inputs,max_tokens)
        if task=='material_prepare':
            started.set()
            await release.wait()
        return result
    monkeypatch.setattr(FixtureProvider,'generate_json',paused)
    from offerpilot.worker.main import once
    worker=asyncio.create_task(once())
    await asyncio.wait_for(started.wait(),5)
    deleted=await client.request('DELETE','/api/v1/resume-versions/'+profile['resume_version_id'],json={'confirmed':True},headers={'Idempotency-Key':str(uuid4())})
    assert deleted.status_code==202,deleted.text
    assert (await client.post('/api/v1/me/exports',json={'format':'json'},headers={'Idempotency-Key':str(uuid4())})).status_code==409
    release.set()
    await worker
    await drain()
    status=(await client.get('/api/v1/deletion-requests/'+deleted.json()['id'])).json()
    assert status['status']=='succeeded',status
    run=(await client.get('/api/v1/runs/'+r.json()['id'])).json()
    assert run['status']=='cancelled',run
    assert not (await client.get('/api/v1/applications/'+app['id']+'/preparation-bundles')).json()['items']
    export=await client.post('/api/v1/me/exports',json={'format':'json'},headers={'Idempotency-Key':str(uuid4())})
    await drain()
    downloaded=await client.get('/api/v1/me/exports/'+export.json()['id']+'/download')
    assert downloaded.status_code==200,downloaded.text
    assert '独有合成任务列表' not in downloaded.text


async def test_account_delete_receipt_and_admin_isolation(client:httpx.AsyncClient):
    owner=await account(client)
    assert (await client.get('/api/v1/admin/overview')).status_code==403
    await base(client)
    response=await client.request('DELETE','/api/v1/me',json={'password':'synthetic-password-123','confirmed':True},headers={'Idempotency-Key':str(uuid4())})
    assert response.status_code==202,response.text
    receipt=response.json()
    assert (await client.get('/api/v1/auth/me')).status_code==401
    await drain()
    status=await client.get('/api/v1/deletion-requests/'+receipt['id'],headers={'X-Deletion-Receipt':receipt['receipt']})
    assert status.status_code==200 and status.json()['status']=='succeeded',status.text
    async with Session() as db:assert await db.get(User,owner) is None
    assert (await client.get('/api/v1/jobs',headers={'X-Deletion-Receipt':receipt['receipt']})).status_code==401
