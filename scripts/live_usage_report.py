"""Sanitized call evidence from the isolated acceptance database, never credentials."""
import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy import select

from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import Session
from offerpilot.modules.identity.models import User
from offerpilot.modules.runs.models import AgentRun, ProviderCall


async def main():
    if settings().public_origin != 'http://localhost:8082':
        raise SystemExit('Only the isolated acceptance stack may export test metadata')
    async with Session() as db:
        user=await db.scalar(select(User).where(User.username.like('live_%')).order_by(User.created_at.desc()).limit(1))
        if not user:
            raise SystemExit('No synthetic acceptance user')
        runs=await db.scalars(select(AgentRun).where(AgentRun.owner_id==user.id).order_by(AgentRun.created_at))
        run_data=[{'id':str(r.id),'kind':r.kind,'status':r.status,'model':r.model,'prompt_version':r.prompt_version,'started_at':r.started_at.isoformat() if r.started_at else None,'completed_at':r.completed_at.isoformat() if r.completed_at else None,'error_code':r.error_code} for r in runs]
        calls=await db.scalars(select(ProviderCall).where(ProviderCall.owner_id==user.id).order_by(ProviderCall.created_at))
        call_data=[{'id':str(c.id),'run_id':str(c.run_id),'provider':c.provider,'step_key':c.step_key,'model':c.model,'response_model':c.response_model,'prompt_version':c.prompt_version,'status':c.status,'usage':c.usage,'error_code':c.error_code} for c in calls]
    print(json.dumps({'time':datetime.now(UTC).isoformat(),'synthetic_user':user.username,'origin':'http://localhost:8082','runs':run_data,'calls':call_data},ensure_ascii=False,indent=2))


if __name__=='__main__':
    asyncio.run(main())
