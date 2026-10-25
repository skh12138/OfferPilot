from uuid import UUID

from fastapi import APIRouter
from offerpilot.api.deps import DB, Current, Write
from offerpilot.api.errors import DomainError
from offerpilot.api.schemas import Page
from offerpilot.infrastructure.owned import check_revision, get_owned, lock_owner
from offerpilot.modules.jobs.models import DuplicateReview, Job, JobMergeEvent
from offerpilot.modules.jobs.schemas import DuplicateDecision, DuplicateDTO, MergeDTO
from sqlalchemy import select

router = APIRouter(tags=["duplicates"])


@router.get("/duplicate-reviews", response_model=Page[DuplicateDTO])
async def duplicates(user: Current, db: DB) -> Page[DuplicateDTO]:
    rows = await db.scalars(
        select(DuplicateReview)
        .where(DuplicateReview.owner_id == user.id)
        .order_by(DuplicateReview.id)
        .limit(100)
    )
    return Page(items=[DuplicateDTO.model_validate(r) for r in rows])


@router.post("/duplicate-reviews/{review_id}/decision", response_model=DuplicateDTO)
async def decide(
    review_id: UUID, data: DuplicateDecision, user: Current, db: DB, _: Write
) -> DuplicateDTO:
    await lock_owner(db, user.id)
    row = await get_owned(db, DuplicateReview, user.id, review_id, lock=True)
    check_revision(row.revision, data.expected_revision)
    if row.decision:
        raise DomainError("duplicate_already_decided", "已处理，合并可在记录中撤销")
    if data.decision == "merge":
        source = await get_owned(db, Job, user.id, row.right_id, lock=True)
        target = await get_owned(db, Job, user.id, row.left_id, lock=True)
        if source.merged_into_id or target.merged_into_id:
            raise DomainError("merge_conflict", "岗位已有合并关系，请先撤销")
        source.merged_into_id, source.revision = target.id, source.revision + 1
        db.add(
            JobMergeEvent(
                owner_id=user.id, source_id=source.id, target_id=target.id, reason=data.reason
            )
        )
    row.decision, row.revision = data.decision, row.revision + 1
    await db.commit()
    return DuplicateDTO.model_validate(row)


@router.get("/job-merges", response_model=Page[MergeDTO])
async def merges(user: Current, db: DB) -> Page[MergeDTO]:
    rows = await db.scalars(
        select(JobMergeEvent)
        .where(JobMergeEvent.owner_id == user.id)
        .order_by(JobMergeEvent.created_at.desc())
        .limit(100)
    )
    return Page(items=[MergeDTO.model_validate(r) for r in rows])


@router.post("/job-merges/{merge_id}/undo", response_model=MergeDTO)
async def undo(merge_id: UUID, user: Current, db: DB, _: Write) -> MergeDTO:
    await lock_owner(db, user.id)
    row = await get_owned(db, JobMergeEvent, user.id, merge_id, lock=True)
    job = await get_owned(db, Job, user.id, row.source_id, lock=True)
    if not row.undone:
        job.merged_into_id, job.revision, row.undone = None, job.revision + 1, True
    await db.commit()
    return MergeDTO.model_validate(row)
