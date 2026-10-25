from uuid import uuid4
from datetime import UTC,datetime,timedelta
import httpx
from conftest import account,drain


async def new_application(c):
    response=await c.post('/api/v1/applications',json={'title':'合成开发','company':'合成公司'},headers={'Idempotency-Key':str(uuid4())})
    assert response.status_code==201,response.text
    return response.json()


async def test_submission_snapshot_and_progress_rounds(client:httpx.AsyncClient):
    await account(client)
    profile=(await client.post('/api/v1/profile-versions',json={'preferences':{'days_per_week':3},'reason':'投递版'})).json()
    app=await new_application(client)
    payload={'expected_revision':app['revision'],'actual_submission_confirmed':True,'submitted_at':datetime.now(UTC).isoformat(),'channel':'合成官网','profile_version_id':profile['id'],'missing_materials':False}
    key=str(uuid4())
    sub=await client.post('/api/v1/applications/'+app['id']+'/submissions',json=payload,headers={'Idempotency-Key':key})
    assert sub.status_code==201,sub.text
    assert (await client.post('/api/v1/applications/'+app['id']+'/submissions',json=payload,headers={'Idempotency-Key':key})).json()['id']==sub.json()['id']
    await client.post('/api/v1/profile-versions',json={'preferences':{'days_per_week':5},'reason':'新资料'})
    assert (await client.get('/api/v1/applications/'+app['id']+'/submissions')).json()['items'][0]['profile_version_id']==profile['id']
    app=(await client.get('/api/v1/applications/'+app['id'])).json()
    checked=await client.post('/api/v1/applications/'+app['id']+'/progress-checks',json={'expected_revision':app['revision'],'checked_at':datetime.now(UTC).isoformat(),'observed_status':'等待筛选','changed':False,'user_confirmed':True})
    assert checked.json()['stage']=='submitted' and checked.json()['last_checked_at']
    rnd=await client.post('/api/v1/applications/'+app['id']+'/rounds',json={'name':'直接技术面','reminders_enabled':True,'planned_at':(datetime.now(UTC)+timedelta(days=2)).isoformat()})
    assert rnd.status_code==201,rnd.text
    row=rnd.json()
    updated=await client.patch('/api/v1/rounds/'+row['id'],json={'name':row['name'],'expected_revision':row['revision'],'planned_at':(datetime.now(UTC)+timedelta(days=3)).isoformat(),'reminders_enabled':True,'reason':'改期'})
    assert updated.status_code==200,updated.text
    tasks=(await client.get('/api/v1/tasks',params={'application_id':app['id']})).json()['items']
    assert len(tasks)==1 and tasks[0]['due_at']==updated.json()['planned_at']
    conflict=await client.patch('/api/v1/rounds/'+row['id'],json={'name':'过时请求','expected_revision':row['revision'],'reason':'旧请求'})
    assert conflict.status_code==412


async def test_prepare_approval_basis_and_idempotency(client:httpx.AsyncClient):
    await account(client)
    r=await client.post('/api/v1/resume-versions',json={'title':'合成','text':'使用 Vue3 完成任务列表。\n计划学习模型。'},headers={'Idempotency-Key':str(uuid4())})
    await drain()
    p=(await client.get('/api/v1/profiles/current')).json()['current']
    for fact in p['facts']:fact['status']='planned' if '计划' in fact['text'] else 'user_confirmed'
    p=(await client.post('/api/v1/profile-versions',json={k:p[k] for k in ['resume_version_id','preferences','facts']}|{'reason':'确认'})).json()
    app=await new_application(client)
    app=(await client.post('/api/v1/applications/'+app['id']+'/preparation-basis',json={'expected_revision':app['revision'],'profile_version_id':p['id'],'reason':'选定资料'})).json()
    run=await client.post('/api/v1/applications/'+app['id']+'/preparation-runs',json={'expected_revision':app['revision']},headers={'Idempotency-Key':str(uuid4())})
    assert run.status_code==202,run.text
    await drain()
    state=(await client.get('/api/v1/runs/'+run.json()['id'])).json()
    assert state['status']=='succeeded',state
    bundle=(await client.get('/api/v1/preparation-bundles/'+state['result']['bundle_id'])).json()
    assert all('计划' not in c['text'] for c in bundle['current']['data']['claims'])
    body={'expected_revision':bundle['revision'],'version_id':bundle['current']['id'],'payload_hash':bundle['current']['payload_hash'],'basis_revision':bundle['current']['basis_revision']}
    approved=await client.post('/api/v1/preparation-bundles/'+bundle['id']+'/approve',json=body,headers={'Idempotency-Key':str(uuid4())})
    assert approved.status_code==200,approved.text
    repeated=await client.post('/api/v1/preparation-bundles/'+bundle['id']+'/approve',json=body,headers={'Idempotency-Key':str(uuid4())})
    assert approved.json()['id']==repeated.json()['id']
    assert len((await client.get('/api/v1/tasks',params={'application_id':app['id']})).json()['items'])==1
    changed=await client.post('/api/v1/applications/'+app['id']+'/preparation-basis',json={'expected_revision':app['revision'],'profile_version_id':None,'reason':'切换'})
    assert changed.status_code==200
    assert (await client.post('/api/v1/preparation-bundles/'+bundle['id']+'/approve',json=body,headers={'Idempotency-Key':str(uuid4())})).status_code==409
