"""Run Playwright against its own API/Worker/PG database, never the development data."""
import os
import subprocess
from pathlib import Path
import psycopg
from psycopg import sql

root=Path(__file__).resolve().parents[1]
os.chdir(root)
url=os.environ.get('E2E_DATABASE_URL','postgresql+psycopg://offerpilot:offerpilot@localhost:55432/offerpilot_test_e2e')
if not url.rsplit('/',1)[-1].startswith('offerpilot_test'):raise SystemExit('E2E database must start with offerpilot_test')
admin=url.rsplit('/',1)[0]+'/postgres'
name=url.rsplit('/',1)[-1]
with psycopg.connect(admin.replace('postgresql+psycopg','postgresql'),autocommit=True) as db:
    if not db.execute('SELECT 1 FROM pg_database WHERE datname=%s',(name,)).fetchone():db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
env={**os.environ,'APP_MODE':'demo','ENVIRONMENT':'development','PUBLIC_ORIGIN':'http://localhost:5179','DATABASE_URL':url,'ALLOW_REGISTRATION':'true','VITE_API_TARGET':'http://127.0.0.1:8011'}
subprocess.run(['.venv/bin/alembic','-c','apps/server/alembic.ini','upgrade','head'],env=env,check=True)
subprocess.run(['pnpm','exec','playwright','test'],env=env,check=True)
