"""Explicit real-provider smoke. Never silently falls back to demo or skips as success."""
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

os.environ['APP_MODE']='live'
from offerpilot.infrastructure.config import settings
cfg=settings()
if not cfg.deepseek_api_key.get_secret_value() or not cfg.tavily_api_key.get_secret_value():
    raise SystemExit('真实验收未执行：需要 DEEPSEEK_API_KEY 和 TAVILY_API_KEY；没有使用 fixtures。')
if not os.environ.get('LIVE_DATABASE_URL'):
    raise SystemExit('真实验收未执行：请设置隔离 LIVE_DATABASE_URL，并迁移及配置至少两个有使用依据的来源策略。')


async def main():
    # Separate process ensures Settings/engine bind to the explicitly selected acceptance database.
    import subprocess
    env={**os.environ,'DATABASE_URL':os.environ['LIVE_DATABASE_URL']}
    if not env['DATABASE_URL'].rsplit('/',1)[-1].startswith('offerpilot_live_acceptance'):
        raise SystemExit('LIVE_DATABASE_URL database name must begin with offerpilot_live_acceptance')
    subprocess.run(['.venv/bin/python','scripts/live_probe.py'],env=env,check=True)


if __name__=='__main__':asyncio.run(main())
