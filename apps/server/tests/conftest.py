import os
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

os.environ['APP_MODE'] = 'test'
os.environ['ENVIRONMENT'] = 'development'
os.environ['PUBLIC_ORIGIN'] = 'http://localhost:5173'
os.environ['ALLOW_REGISTRATION'] = 'true'
os.environ['DATABASE_URL'] = os.environ.get('TEST_DATABASE_URL', 'postgresql+psycopg://offerpilot:offerpilot@localhost:55432/offerpilot_test')
if not os.environ['DATABASE_URL'].rsplit('/', 1)[-1].startswith('offerpilot_test'):
    raise RuntimeError('Refusing tests against a non-test database')

import httpx
import pytest
import pytest_asyncio
from offerpilot.api.app import app
from offerpilot.infrastructure.db import engine


@pytest.fixture(scope='session', autouse=True)
def migrations():
    subprocess.run([str(Path('.venv/bin/alembic')), '-c', 'apps/server/alembic.ini', 'upgrade', 'head'], check=True)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost:5173', headers={'Origin':'http://localhost:5173'}) as c:
        csrf = (await c.get('/api/v1/auth/csrf')).json()['csrf_token']
        c.headers['X-CSRF-Token'] = csrf
        yield c
    await engine.dispose()


async def account(client: httpx.AsyncClient) -> str:
    name = f'u_{uuid4().hex[:16]}'
    credentials = {'username':name,'password':'synthetic-password-123'}
    response = await client.post('/api/v1/auth/register', json=credentials)
    assert response.status_code == 201, response.text
    response = await client.post('/api/v1/auth/login', json=credentials)
    assert response.status_code == 200, response.text
    await client.post('/api/v1/me/model-consent',json={'granted':True})
    return response.json()['id']


async def drain():
    from offerpilot.worker.main import once
    for _ in range(30):
        if not await once():
            return
    raise AssertionError('Worker did not drain')
