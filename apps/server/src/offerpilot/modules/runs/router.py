import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse
from offerpilot.api.deps import DB, Current, Write
from offerpilot.api.errors import DomainError
from offerpilot.api.schemas import Page
from offerpilot.infrastructure.db import Session
from offerpilot.infrastructure.owned import get_owned
from offerpilot.modules.runs import service
from offerpilot.modules.runs.models import TERMINAL, AgentRun, RunEvent, RunStatus
from offerpilot.modules.runs.schemas import RunDTO
from sqlalchemy import select

router = APIRouter(tags=["runs"])


@router.get("/runs/{run_id}", response_model=RunDTO)
async def read_run(run_id: UUID, user: Current, db: DB) -> RunDTO:
    return RunDTO.model_validate(await get_owned(db, AgentRun, user.id, run_id))


@router.post("/runs/{run_id}/cancel", response_model=RunDTO)
async def cancel(run_id: UUID, user: Current, db: DB, _: Write) -> RunDTO:
    return RunDTO.model_validate(await service.cancel(db, user.id, run_id))


@router.post("/runs/{run_id}/retry", response_model=RunDTO, status_code=202)
async def retry(
    run_id: UUID,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> RunDTO:
    original = await get_owned(db, AgentRun, user.id, run_id)
    if original.status not in {RunStatus.FAILED, RunStatus.PARTIAL, RunStatus.CANCELLED}:
        raise DomainError("run_not_retryable", "仅能重试失败、部分完成或取消的运行")
    inputs = dict(original.inputs)
    inputs["retry_of"] = str(original.id)
    run = await service.enqueue(
        db,
        user.id,
        original.kind,
        inputs,
        idempotency_key,
        profile_id=original.profile_version_id,
        resume_id=original.resume_version_id,
        application_id=original.application_id,
        commit=False,
    )
    run.retry_of = original.id
    await db.commit()
    return RunDTO.model_validate(run)


@router.get("/runs/{run_id}/events")
async def events(
    run_id: UUID,
    request: Request,
    user: Current,
    db: DB,
    after: int = Query(default=0, ge=0),
    last_event_id: int | None = Header(default=None),
) -> StreamingResponse:
    await get_owned(db, AgentRun, user.id, run_id)
    owner = user.id
    from offerpilot.modules.identity.service import token_hash

    session_hash = token_hash(request.cookies.get("op_session", ""))
    start = max(after, last_event_id or 0)
    await db.rollback()

    async def stream() -> AsyncIterator[str]:
        cursor, beats = start, 0
        while True:
            async with Session() as fresh:
                # Re-check session/account access for every delivery, including after deletion.
                from offerpilot.infrastructure.db import now
                from offerpilot.modules.identity.models import SessionToken, User

                active = await fresh.get(User, owner)
                session_ok = await fresh.scalar(
                    select(SessionToken).where(
                        SessionToken.owner_id == owner,
                        SessionToken.token_hash == session_hash,
                        SessionToken.expires_at > now(),
                    )
                )
                if active is None or active.disabled or not session_ok:
                    return
                run = await get_owned(fresh, AgentRun, owner, run_id)
                rows = list(
                    await fresh.scalars(
                        select(RunEvent)
                        .where(
                            RunEvent.owner_id == owner,
                            RunEvent.run_id == run_id,
                            RunEvent.seq > cursor,
                        )
                        .order_by(RunEvent.seq)
                    )
                )
                terminal = RunStatus(run.status) in TERMINAL
            for row in rows:
                cursor = row.seq
                yield f"id: {row.seq}\nevent: {row.event_type}\ndata: {json.dumps(row.data, ensure_ascii=False)}\n\n"
            if terminal:
                return
            beats += 1
            if beats % 15 == 0:
                yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@router.get("/runs", response_model=Page[RunDTO])
async def runs(user: Current, db: DB, kind: str | None = None) -> "Page[RunDTO]":
    query = (
        select(AgentRun)
        .where(AgentRun.owner_id == user.id)
        .order_by(AgentRun.created_at.desc(), AgentRun.id)
    )
    if kind:
        query = query.where(AgentRun.kind == kind)
    rows = await db.scalars(query.limit(100))
    return Page(items=[RunDTO.model_validate(r) for r in rows])
