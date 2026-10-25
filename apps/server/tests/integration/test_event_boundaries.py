from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete

from conftest import account
from offerpilot.infrastructure.db import Session
from offerpilot.modules.identity.models import LoginFailure
from offerpilot.modules.identity.service import token_hash


async def test_login_origin_wrong_password_and_rate_limit(client: httpx.AsyncClient):
    username = 'synthetic_' + uuid4().hex[:16]
    credentials = {'username': username, 'password': 'synthetic-wrong-password'}
    assert (await client.post('/api/v1/auth/login', json=credentials, headers={'Origin':'https://untrusted.example'})).status_code == 403
    try:
        for _ in range(10):
            response = await client.post('/api/v1/auth/login', json=credentials)
            assert response.status_code == 401 and 'password_hash' not in response.text
        assert (await client.post('/api/v1/auth/login', json=credentials)).status_code == 429
    finally:
        async with Session() as db:
            await db.execute(delete(LoginFailure).where(LoginFailure.account_key == token_hash(username)))
            await db.commit()


@pytest.mark.parametrize('task_action', ['keep', 'cancel', 'detach'])
async def test_close_reopen_and_stale_application_events(client: httpx.AsyncClient, task_action: str):
    await account(client)
    app = (await client.post('/api/v1/applications', json={'title':'合成流程边界','company':'合成'}, headers={'Idempotency-Key':str(uuid4())})).json()
    task = (await client.post('/api/v1/tasks', json={'title':'合成未完任务','application_id':app['id']})).json()
    payload = {'expected_revision':app['revision'],'event_type':'advance','to_stage':'preparing','reason':'本人开始准备','source':'user','happened_at':datetime.now(UTC).isoformat()}
    updated = await client.post('/api/v1/applications/'+app['id']+'/events', json=payload, headers={'Idempotency-Key':str(uuid4())})
    assert updated.status_code == 200, updated.text
    assert (await client.post('/api/v1/applications/'+app['id']+'/events', json=payload, headers={'Idempotency-Key':str(uuid4())})).status_code == 412
    payload.update(expected_revision=updated.json()['revision'], event_type='correction', to_stage='interested', reason='补录更正')
    corrected = await client.post('/api/v1/applications/'+app['id']+'/events', json=payload, headers={'Idempotency-Key':str(uuid4())})
    assert corrected.status_code == 200
    payload.update(expected_revision=corrected.json()['revision'], event_type='advance', to_stage='closed', close_reason='本人结束', task_action=task_action)
    closed = await client.post('/api/v1/applications/'+app['id']+'/events', json=payload, headers={'Idempotency-Key':str(uuid4())})
    assert closed.status_code == 200, closed.text
    tasks = (await client.get('/api/v1/tasks')).json()['items']
    remaining = next(t for t in tasks if t['id'] == task['id'])
    assert remaining['status'] == ('cancelled' if task_action == 'cancel' else 'todo')
    assert remaining['application_id'] == (None if task_action == 'detach' else app['id'])
    payload.update(expected_revision=closed.json()['revision'], event_type='reopen', to_stage='interested', reason='本人重新考虑')
    reopened = await client.post('/api/v1/applications/'+app['id']+'/events', json=payload, headers={'Idempotency-Key':str(uuid4())})
    assert reopened.status_code == 200 and reopened.json()['stage'] == 'interested'
    assert len((await client.get('/api/v1/applications/'+app['id']+'/events')).json()['items']) == 4
