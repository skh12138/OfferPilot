from uuid import UUID

from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.owned import check_revision
from offerpilot.modules.discovery.models import SourcePolicy
from offerpilot.modules.discovery.schemas import PolicyInput, PolicyPatch
from offerpilot.modules.runs.models import AuditEvent
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


async def save_policy(
    db: AsyncSession, admin: UUID, data: PolicyInput, policy_id: UUID | None = None
) -> SourcePolicy:
    from offerpilot.providers.urls import canonical_url

    canonical_url("https://" + data.domain)
    if policy_id:
        row = await db.scalar(
            select(SourcePolicy).where(SourcePolicy.id == policy_id).with_for_update()
        )
        if row is None:
            raise DomainError("not_found", "来源策略不存在", 404)
        if not isinstance(data, PolicyPatch):
            raise DomainError("revision_required", "缺少版本", 422)
        check_revision(row.revision, data.expected_revision)
        row.revision += 1
        for field, value in data.model_dump(exclude={"expected_revision"}).items():
            setattr(row, field, value)
    else:
        existing = await db.scalar(select(SourcePolicy).where(SourcePolicy.domain == data.domain))
        if existing:
            raise DomainError("policy_exists", "域名已有策略")
        row = SourcePolicy(**data.model_dump())
        db.add(row)
    await db.flush()
    db.add(
        AuditEvent(
            owner_id=admin,
            action="source_policy_changed",
            target_id=row.id,
            details=f"{row.domain}:{row.mode}:r{row.revision}",
        )
    )
    if row.mode != "extract_allowed" or not row.store_text:
        # Retention restriction is global public-source maintenance. Never join personal profiles.
        from offerpilot.modules.jobs.models import JobVersion, TextSnapshot

        snapshots = list(
            await db.scalars(
                select(TextSnapshot.id).where(
                    TextSnapshot.url.like(f"https://{row.domain}/%")
                    | TextSnapshot.url.like(f"http://{row.domain}/%")
                )
            )
        )
        await db.execute(
            update(TextSnapshot)
            .where(TextSnapshot.id.in_(snapshots))
            .values(text=None, paragraphs={})
        )
        versions = await db.scalars(select(JobVersion).where(JobVersion.snapshot_id.in_(snapshots)))
        from offerpilot.modules.jobs.schemas import JobExtraction

        for version in versions:
            data_job = JobExtraction.model_validate(version.data)
            data_job.conditions, data_job.requirements = {}, []
            data_job.field_evidence = {}
            data_job.classification = "unknown"
            data_job.responsibilities = []
            data_job.missing_fields = ["来源策略限制，正文与衍生证据已清理"]
            version.data = data_job.model_dump(mode="json")
        from offerpilot.modules.interview.models import InterviewSource

        await db.execute(
            update(InterviewSource)
            .where(
                InterviewSource.url.like(f"https://{row.domain}/%")
                | InterviewSource.url.like(f"http://{row.domain}/%")
            )
            .values(evidence=None, content_status="metadata_only")
        )
    from offerpilot.modules.operations.retention import tighten_retention

    await tighten_retention(db, row)
    await db.commit()
    return row
