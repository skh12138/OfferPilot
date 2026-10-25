import os
import subprocess
from datetime import UTC,datetime
from uuid import uuid4
import psycopg
from psycopg import sql


def test_empty_database_and_stage_upgrade_preserve_data():
    base=os.environ['DATABASE_URL'].replace('postgresql+psycopg','postgresql').rsplit('/',1)[0]
    name='offerpilot_test_upgrade_'+uuid4().hex[:12]
    with psycopg.connect(base+'/postgres',autocommit=True) as admin:admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    url=base+'/'+name
    env={**os.environ,'DATABASE_URL':url.replace('postgresql://','postgresql+psycopg://')}
    def migrate(revision):subprocess.run(['.venv/bin/alembic','-c','apps/server/alembic.ini','upgrade',revision],env=env,check=True,capture_output=True)
    user_id=uuid4()
    try:
        migrate('0001')
        with psycopg.connect(url) as db:db.execute("INSERT INTO deployment_metadata(key,value) VALUES ('upgrade_sentinel','preserved')")
        migrate('0002')
        with psycopg.connect(url) as db:db.execute("INSERT INTO users(id,created_at,username,password_hash,is_admin,disabled,timezone) VALUES (%s,%s,%s,%s,false,false,'Asia/Shanghai')",(user_id,datetime.now(UTC),'synthetic_migration_'+uuid4().hex[:8],'not-a-login-hash'))
        for revision in ['0003','0004','0005','0006','0007','0008','0009','0010']:
            migrate(revision)
            with psycopg.connect(url) as db:
                assert db.execute("SELECT value FROM deployment_metadata WHERE key='upgrade_sentinel'").fetchone()[0]=='preserved'
                assert db.execute('SELECT id FROM users WHERE id=%s',(user_id,)).fetchone()[0]==user_id
        with psycopg.connect(url) as db:
            tables={row[0] for row in db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")}
            assert {'questions','answer_feedback','tasks','run_steps','deletion_requests','offer_events','search_candidate_analyses'}<=tables
        subprocess.run(['.venv/bin/alembic','-c','apps/server/alembic.ini','check'],env=env,check=True,capture_output=True)
    finally:
        with psycopg.connect(base+'/postgres',autocommit=True) as admin:admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
