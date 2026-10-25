from uuid import uuid4
import httpx
from conftest import account, drain


async def test_identity_versions_isolation(client: httpx.AsyncClient):
    assert (await client.get('/api/v1/jobs')).status_code == 401
    await account(client)
    response = await client.post('/api/v1/resume-versions', json={'title':'合成简历','text':'使用 Vue3 完成任务列表与筛选。\n计划学习 Agent。'},headers={'Idempotency-Key':str(uuid4())})
    assert response.status_code == 202, response.text
    await drain()
    run = (await client.get('/api/v1/runs/'+response.json()['id'])).json()
    assert run['status'] == 'succeeded', run
    profile = (await client.get('/api/v1/profiles/current')).json()['current']
    assert all(f['status']=='unconfirmed' for f in profile['facts'])
    for fact in profile['facts']:
        fact['status'] = 'planned' if '计划' in fact['text'] else 'user_confirmed'
    new = await client.post('/api/v1/profile-versions',json={k:profile[k] for k in ['resume_version_id','preferences','facts']}|{'reason':'逐条确认'})
    assert new.status_code == 201, new.text
    old_id=profile['id']
    await account(client)
    assert (await client.post('/api/v1/profile-versions/'+old_id+'/revocations',json={'fact_id':str(uuid4()),'reason':'test'})).status_code == 404
    assert not (await client.get('/api/v1/resume-versions')).json()['items']


async def test_csrf_logout_and_unknown_fields(client: httpx.AsyncClient):
    await account(client)
    assert (await client.post('/api/v1/auth/logout',headers={'X-CSRF-Token':''})).status_code == 403
    assert (await client.post('/api/v1/profile-versions',json={'owner_id':str(uuid4()),'reason':'bad'})).status_code == 422
    assert (await client.post('/api/v1/auth/logout')).status_code == 200
    assert (await client.get('/api/v1/auth/me')).status_code == 401


async def test_job_parse_confirm_and_match(client: httpx.AsyncClient):
    await account(client)
    response = await client.post('/api/v1/job-imports',json={'text':'合成 Python 实习\n每周至少4天，持续3个月\n要求 Python、JavaScript','url':'https://example.com/job?id=1&utm_source=test'},headers={'Idempotency-Key':str(uuid4())})
    assert response.status_code == 202, response.text
    await drain()
    run=(await client.get('/api/v1/runs/'+response.json()['id'])).json()
    assert run['status']=='succeeded',run
    job_id=run['result']['job_ids'][0]
    job=(await client.get('/api/v1/jobs/'+job_id)).json()
    corrected=await client.post('/api/v1/jobs/'+job_id+'/versions',json={'expected_revision':job['revision'],'data':job['current']['data'],'reason':'人工校对','confirm_fields':True})
    assert corrected.status_code==201,corrected.text
    p=await client.post('/api/v1/profile-versions',json={'preferences':{'days_per_week':3},'reason':'偏好'})
    response=await client.post('/api/v1/matches',json={'profile_version_id':p.json()['id'],'job_version_id':corrected.json()['id']})
    assert response.json()['overall']=='fail',response.text
    assert len((await client.get('/api/v1/jobs/'+job_id)).json()['versions'])==2


async def test_raw_resume_without_consent_and_revocation_across_versions(client: httpx.AsyncClient):
    from uuid import UUID
    from offerpilot.infrastructure.db import Session
    from offerpilot.modules.profiles.service import confirmed_facts
    owner = UUID(await account(client))
    await client.post('/api/v1/me/model-consent', json={'granted': False})
    payload = {'title': '仅保存合成文本', 'text': '合成事实', 'parse': False}
    headers = {'Idempotency-Key': str(uuid4())}
    first = await client.post('/api/v1/resume-versions', json=payload, headers=headers)
    second = await client.post('/api/v1/resume-versions', json=payload, headers=headers)
    assert first.status_code == 202 and first.json()['id'] == second.json()['id']
    assert first.json()['text'] == '合成事实'
    fact_id = str(uuid4())
    profile = {'reason':'本人确认', 'resume_version_id': first.json()['id'], 'preferences': {},
               'facts': [{'fact_id':fact_id,'text':'合成事实','status':'user_confirmed',
                          'evidence':{'paragraph_id':'p1','quote':'合成事实','source_kind':'user_provided'}}]}
    old = await client.post('/api/v1/profile-versions', json=profile)
    assert old.status_code == 201, old.text
    profile['facts'][0]['status'] = 'planned'
    downgraded = await client.post('/api/v1/profile-versions', json=profile)
    assert downgraded.status_code == 201, downgraded.text
    current = (await client.get('/api/v1/profiles/current')).json()['current']
    assert fact_id in current['revoked_fact_ids']
    async with Session() as db:
        assert await confirmed_facts(db, owner, UUID(old.json()['id'])) == []


async def test_user_job_edit_keeps_assertion_distinct_from_model(client: httpx.AsyncClient):
    await account(client)
    response = await client.post('/api/v1/job-imports', json={'text':'合成岗位\n要求 Python'}, headers={'Idempotency-Key':str(uuid4())})
    await drain()
    run = (await client.get('/api/v1/runs/'+response.json()['id'])).json()
    job_id = run['result']['job_ids'][0]
    job = (await client.get('/api/v1/jobs/'+job_id)).json()
    data = job['current']['data']
    data['title'] = '本人补充的合成名称'
    data['conditions']['days_per_week'] = {'value':3,'review_status':'unreviewed','strength':'hard'}
    data['conditions']['cities'] = {'value':['杭州'],'review_status':'conflict','strength':'hard'}
    edited = await client.post('/api/v1/jobs/'+job_id+'/versions', json={'expected_revision':job['revision'],'data':data,'reason':'本人补充','confirm_fields':True})
    assert edited.status_code == 201, edited.text
    provenance = edited.json()['data']['field_evidence']['title']
    assert provenance['source_kind'] == 'user_asserted' and provenance['review_status'] == 'confirmed'
    conditions = edited.json()['data']['conditions']
    assert conditions['days_per_week']['evidence_status'] == 'user_asserted'
    assert conditions['days_per_week']['review_status'] == 'confirmed'
    assert conditions['cities']['review_status'] == 'conflict'
