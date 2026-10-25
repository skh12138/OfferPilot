"""Create a synthetic admin only in the explicitly isolated 8082 acceptance stack."""
import asyncio
import json
import secrets
from uuid import uuid4

from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import Session
from offerpilot.modules.identity.schemas import Credentials
from offerpilot.modules.identity.service import register


async def main():
    cfg=settings()
    if cfg.app_mode != 'live' or cfg.public_origin != 'http://localhost:8082':
        raise SystemExit('Refusing setup outside the explicit isolated live acceptance origin')
    credentials=Credentials(username='live_'+uuid4().hex[:16],password=secrets.token_urlsafe(32))
    async with Session() as db:
        user=await register(db,credentials,admin=True)
    print(json.dumps({'username':user.username,'password':credentials.password,'origin':cfg.public_origin}))


if __name__=='__main__':
    asyncio.run(main())
