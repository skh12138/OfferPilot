import asyncio
import json
import logging
import os
import socket
from contextlib import suppress
from uuid import UUID

from offerpilot.api.errors import DomainError
from offerpilot.infrastructure import models as models
from offerpilot.infrastructure.db import Session, now
from offerpilot.modules.runs.models import AgentRun, RunStatus
from offerpilot.modules.runs.service import event
from offerpilot.providers.base import ProviderError
from offerpilot.worker.queue import LeaseLost, claim, heartbeat
from offerpilot.workflows.graphs import execute
from sqlalchemy import select

log = logging.getLogger("offerpilot.worker")


async def pulse(run_id: UUID, token: UUID) -> None:
    while True:
        await asyncio.sleep(15)
        if not await heartbeat(run_id, token):
            return


async def finish_error(run_id: UUID, token: UUID, code: str) -> None:
    async with Session() as db:
        row = await db.scalar(
            select(AgentRun)
            .where(
                AgentRun.id == run_id,
                AgentRun.lease_token == token,
                AgentRun.status == RunStatus.RUNNING,
            )
            .with_for_update()
        )
        if not row or not row.lease_expires_at or row.lease_expires_at <= now():
            return
        row.status = (
            RunStatus.CANCELLED
            if row.cancel_requested_at or code == "run_cancelled"
            else RunStatus.PARTIAL
            if row.result
            else RunStatus.FAILED
        )
        row.error_code, row.completed_at = code, now()
        event(
            db,
            row,
            "run_cancelled" if row.status == RunStatus.CANCELLED else "run_failed",
            {"code": code},
        )
        await db.commit()


async def once(worker_id: str = "test-worker") -> bool:
    job = await claim(worker_id)
    if not job:
        return False
    run_id, token = job
    heart = asyncio.create_task(pulse(run_id, token))
    try:
        await execute(run_id, token)
    except LeaseLost:
        log.info(json.dumps({"run_id": str(run_id), "error_type": "lease_lost"}))
    except (DomainError, ProviderError) as exc:
        await finish_error(run_id, token, exc.code)
    except Exception as exc:
        # Unexpected exceptions are failures, never fabricated successes. Log type only, no inputs.
        log.error(json.dumps({"run_id": str(run_id), "error_type": type(exc).__name__}))
        await finish_error(run_id, token, "internal_execution_error")
        if os.environ.get("APP_MODE") == "test":
            raise
    finally:
        heart.cancel()
        with suppress(asyncio.CancelledError):
            await heart
    return True


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    print("OfferPilot worker ready", flush=True)
    while True:
        from offerpilot.modules.control.exporting import maintenance

        await maintenance()
        if not await once(worker_id):
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
