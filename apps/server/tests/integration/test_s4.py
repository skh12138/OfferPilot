from uuid import uuid4
import httpx
from conftest import account,drain


async def study_package(client:httpx.AsyncClient):
    r=await client.post('/api/v1/job-imports',json={'text':'合成技术实习\n要求：Python API 异常处理'},headers={'Idempotency-Key':str(uuid4())})
    await drain()
    run=(await client.get('/api/v1/runs/'+r.json()['id'])).json()
    job=(await client.get('/api/v1/jobs/'+run['result']['job_ids'][0])).json()
    r=await client.post('/api/v1/study-package-runs',json={'job_version_id':job['current_version_id'],'count':5},headers={'Idempotency-Key':str(uuid4())})
    assert r.status_code==202,r.text
    await drain()
    run=(await client.get('/api/v1/runs/'+r.json()['id'])).json()
    assert run['status']=='succeeded',run
    return (await client.get('/api/v1/study-packages/'+run['result']['study_package_id'])).json()


async def test_study_source_adoption_answer_feedback_review(client:httpx.AsyncClient):
    await account(client)
    package=await study_package(client)
    version=package['current']
    assert len(version['questions'])==5
    assert all(q['source_kind']=='generated_for_target' for q in version['questions'])
    assert 'answer_guidance' not in version['questions'][0]
    assert '面经正文' in ''.join(version['limitations'])
    payload={'expected_revision':package['revision'],'version_id':version['id'],'payload_hash':version['payload_hash'],'basis_revision':version['basis_revision']}
    for _ in range(2):
        result=await client.post('/api/v1/study-packages/'+package['id']+'/adopt',json=payload,headers={'Idempotency-Key':str(uuid4())})
        assert result.status_code==200,result.text
    reviews=(await client.get('/api/v1/review-items')).json()['items']
    assert len(reviews)==5 and all(r['mastery']=='new' for r in reviews)
    question=version['questions'][0]
    assert (await client.get('/api/v1/questions/'+question['id']+'/guidance')).status_code==200
    assert all(r['mastery']=='new' for r in (await client.get('/api/v1/review-items')).json()['items'])
    answer=await client.post('/api/v1/questions/'+question['id']+'/attempts',json={'answer':'合成回答：请求采用幂等键，超时后查询持久化结果。'},headers={'Idempotency-Key':str(uuid4())})
    assert answer.status_code==201,answer.text
    await drain()
    response=(await client.get('/api/v1/attempts/'+answer.json()['id']+'/feedback')).json()
    assert len(response['items'])==1 and response['items'][0]['data']['issues']
    review=reviews[0]
    response=await client.patch('/api/v1/review-items/'+review['id'],json={'expected_revision':review['revision'],'mastery':'needs_review','user_correction':'模型漏看了幂等设计'})
    assert response.status_code==200 and response.json()['mastery']=='needs_review'


async def test_answer_survives_feedback_consent_failure(client:httpx.AsyncClient):
    await account(client)
    package=await study_package(client)
    await client.post('/api/v1/me/model-consent',json={'granted':False})
    question=package['current']['questions'][0]
    response=await client.post('/api/v1/questions/'+question['id']+'/attempts',json={'answer':'这个回答必须被保留'},headers={'Idempotency-Key':str(uuid4())})
    assert response.status_code==201,response.text
    assert response.json()['feedback_error_code']=='model_consent_required'
    assert (await client.get('/api/v1/attempts/'+response.json()['id'])).json()['answer']=='这个回答必须被保留'
