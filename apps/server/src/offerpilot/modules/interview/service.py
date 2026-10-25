from datetime import date
from uuid import UUID

from offerpilot.api.errors import DomainError
from offerpilot.api.schemas import digest
from offerpilot.infrastructure.owned import check_revision, get_owned, lock_owner
from offerpilot.modules.applications.models import Application, AssessmentRound
from offerpilot.modules.interview.models import (
    InterviewSource,
    Question,
    ReviewItem,
    StudyPackage,
    StudyPackageVersion,
)
from offerpilot.modules.interview.rules import next_review, validate_questions
from offerpilot.modules.interview.schemas import (
    AdoptInput,
    QuestionDTO,
    QuestionInput,
    ReviewPatch,
    StudyDTO,
    StudyEdit,
    StudyInput,
    StudyPayload,
    StudyVersionDTO,
)
from offerpilot.modules.jobs.models import JobVersion
from offerpilot.modules.jobs.schemas import JobExtraction
from offerpilot.modules.profiles.service import confirmed_facts, valid_profile
from offerpilot.modules.runs.service import idempotent, remember
from offerpilot.modules.tasks.models import Task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def question_dto(row: Question) -> QuestionDTO:
    return QuestionDTO(
        id=row.id,
        **QuestionInput.model_validate(row.data).model_dump(
            exclude={"hints", "rubric", "answer_guidance", "follow_ups"}
        ),
    )


async def active_version(db: AsyncSession, owner: UUID, version_id: UUID) -> StudyPackageVersion:
    version = await get_owned(db, StudyPackageVersion, owner, version_id)
    if version.deleted:
        raise DomainError("input_deleted", "训练资料已删除", 404)
    if version.profile_version_id:
        await valid_profile(db, owner, version.profile_version_id)
    payload = StudyPayload.model_validate(version.data)
    current_facts = await confirmed_facts(db, owner, version.profile_version_id)
    if any(
        f not in {fact.fact_id for fact in current_facts}
        for q in payload.questions
        for f in q.fact_ids
    ):
        raise DomainError("input_revoked", "题单引用的事实已撤回，请重新生成")
    return version


async def valid_question(db: AsyncSession, owner: UUID, question_id: UUID) -> Question:
    row = await get_owned(db, Question, owner, question_id)
    await active_version(db, owner, row.package_version_id)
    return row


async def version_dto(db: AsyncSession, owner: UUID, row: StudyPackageVersion) -> StudyVersionDTO:
    if row.deleted:
        return StudyVersionDTO(
            id=row.id,
            job_version_id=row.job_version_id,
            profile_version_id=None,
            basis_revision=row.basis_revision,
            topics=[],
            limitations=["资料已删除"],
            questions=[],
            payload_hash=row.payload_hash,
            adopted=row.adopted,
            deleted=True,
        )
    payload = StudyPayload.model_validate(row.data)
    questions = await db.scalars(
        select(Question)
        .where(Question.owner_id == owner, Question.package_version_id == row.id)
        .order_by(Question.created_at, Question.id)
    )
    return StudyVersionDTO(
        id=row.id,
        job_version_id=row.job_version_id,
        profile_version_id=row.profile_version_id,
        basis_revision=row.basis_revision,
        topics=payload.topics,
        limitations=payload.limitations,
        questions=[question_dto(q) for q in questions],
        payload_hash=row.payload_hash,
        adopted=row.adopted,
        deleted=False,
    )


async def detail(db: AsyncSession, owner: UUID, package_id: UUID) -> StudyDTO:
    package = await get_owned(db, StudyPackage, owner, package_id)
    versions = await db.scalars(
        select(StudyPackageVersion)
        .where(StudyPackageVersion.owner_id == owner, StudyPackageVersion.package_id == package.id)
        .order_by(StudyPackageVersion.created_at.desc(), StudyPackageVersion.id)
    )
    items = [await version_dto(db, owner, v) for v in versions]
    return StudyDTO(
        id=package.id,
        application_id=package.application_id,
        revision=package.revision,
        current=next((v for v in items if v.id == package.current_version_id), None),
        versions=items,
    )


async def resolve_basis(
    db: AsyncSession, owner: UUID, data: StudyInput
) -> tuple[UUID, UUID | None, int, UUID | None]:
    job_id, profile_id, basis, submission = data.job_version_id, data.profile_version_id, 1, None
    if data.application_id:
        app = await get_owned(db, Application, owner, data.application_id)
        job_id, profile_id, basis, submission = (
            app.job_version_id,
            app.profile_version_id,
            app.basis_revision,
            app.basis_submission_id,
        )
    if not job_id:
        raise DomainError("job_required", "请先为申请选择岗位版本，或从岗位详情准备", 422)
    await get_owned(db, JobVersion, owner, job_id)
    if profile_id:
        await valid_profile(db, owner, profile_id)
    if data.round_id:
        rnd = await get_owned(db, AssessmentRound, owner, data.round_id)
        if rnd.application_id != data.application_id:
            raise DomainError("invalid_parent", "轮次与申请不一致", 404)
    return job_id, profile_id, basis, submission


async def validate_payload(
    db: AsyncSession, owner: UUID, version: StudyPackageVersion, payload: StudyPayload
) -> None:
    job = await get_owned(db, JobVersion, owner, version.job_version_id)
    facts = await confirmed_facts(db, owner, version.profile_version_id)
    sources = await db.scalars(select(InterviewSource).where(InterviewSource.owner_id == owner))
    validate_questions(
        payload,
        JobExtraction.model_validate(job.data),
        facts,
        {str(s.id): s.evidence for s in sources if s.evidence},
    )


async def store_questions(
    db: AsyncSession, version: StudyPackageVersion, payload: StudyPayload
) -> None:
    for question in payload.questions:
        db.add(
            Question(
                owner_id=version.owner_id,
                package_version_id=version.id,
                data=question.model_dump(mode="json"),
            )
        )


async def edit(
    db: AsyncSession, owner: UUID, package_id: UUID, data: StudyEdit
) -> StudyPackageVersion:
    await lock_owner(db, owner)
    package = await get_owned(db, StudyPackage, owner, package_id, lock=True)
    check_revision(package.revision, data.expected_revision)
    if not package.current_version_id:
        raise DomainError("not_found", "题单不存在", 404)
    previous = await active_version(db, owner, package.current_version_id)
    if package.application_id:
        app = await get_owned(db, Application, owner, package.application_id)
        if app.basis_revision != previous.basis_revision:
            raise DomainError("basis_changed", "基准已变化，请重新生成")
    await validate_payload(db, owner, previous, data.data)
    payload = data.data.model_dump(mode="json")
    version = StudyPackageVersion(
        owner_id=owner,
        package_id=package.id,
        job_version_id=previous.job_version_id,
        profile_version_id=previous.profile_version_id,
        submission_id=previous.submission_id,
        round_id=previous.round_id,
        basis_revision=previous.basis_revision,
        data=payload,
        payload_hash=digest(payload),
        model="user_edited",
        prompt_version=previous.prompt_version,
    )
    db.add(version)
    await db.flush()
    await store_questions(db, version, data.data)
    package.current_version_id, package.revision = version.id, package.revision + 1
    await db.commit()
    return version


async def adopt(
    db: AsyncSession, owner: UUID, package_id: UUID, data: AdoptInput, key: str | None
) -> StudyDTO:
    await lock_owner(db, owner)
    op, payload = f"adopt:{package_id}", data.model_dump(mode="json")
    old = await idempotent(db, owner, op, key, payload)
    if old:
        return await detail(db, owner, old)
    package = await get_owned(db, StudyPackage, owner, package_id, lock=True)
    check_revision(package.revision, data.expected_revision)
    version = await active_version(db, owner, data.version_id)
    if (
        package.current_version_id != version.id
        or version.package_id != package.id
        or version.payload_hash != data.payload_hash
        or digest(version.data) != data.payload_hash
        or version.basis_revision != data.basis_revision
    ):
        raise DomainError("package_changed", "题单或基准变化，请重新审核")
    if package.application_id:
        app = await get_owned(db, Application, owner, package.application_id)
        if app.basis_revision != version.basis_revision:
            raise DomainError("basis_changed", "准备基准已变化")
    await validate_payload(db, owner, version, StudyPayload.model_validate(version.data))
    if not version.adopted:
        rows = await db.scalars(
            select(Question).where(
                Question.owner_id == owner, Question.package_version_id == version.id
            )
        )
        for q in rows:
            question = QuestionInput.model_validate(q.data)
            db.add(
                ReviewItem(
                    owner_id=owner,
                    question_id=q.id,
                    topic=question.topic,
                    next_date=next_review(date.today(), "new"),
                )
            )
            db.add(
                Task(
                    owner_id=owner,
                    application_id=package.application_id,
                    round_id=version.round_id,
                    study_version_id=version.id,
                    business_action_id=f"study:{version.id}:{q.id}",
                    kind="practice",
                    title=question.topic,
                    deliverable="提交一次有依据的回答",
                    acceptance="本人检查反馈并安排复习",
                )
            )
        version.adopted = True
    remember(db, owner, op, str(key), payload, package.id)
    await db.commit()
    return await detail(db, owner, package.id)


async def update_review(
    db: AsyncSession, owner: UUID, item_id: UUID, data: ReviewPatch, today: date
) -> ReviewItem:
    await lock_owner(db, owner)
    row = await get_owned(db, ReviewItem, owner, item_id, lock=True)
    check_revision(row.revision, data.expected_revision)
    await valid_question(db, owner, row.question_id)
    row.mastery, row.next_date = data.mastery, data.next_date or next_review(today, data.mastery)
    row.user_correction, row.revision = data.user_correction, row.revision + 1
    await db.commit()
    return row
