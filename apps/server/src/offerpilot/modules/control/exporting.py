import csv
import io
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import Base, Session, now
from offerpilot.modules.control.models import DeletionRequest, ExportRequest
from offerpilot.worker.context import Context
from offerpilot.worker.queue import guarded
from pydantic import JsonValue, TypeAdapter
from sqlalchemy import select, update

EXPORT_TABLES = {
    "profile_versions",
    "resume_versions",
    "fact_revocations",
    "jobs",
    "job_versions",
    "job_source_links",
    "text_snapshots",
    "job_verifications",
    "job_preferences",
    "match_reports",
    "search_specs",
    "search_candidates",
    "search_candidate_analyses",
    "applications",
    "application_submissions",
    "application_events",
    "assessment_rounds",
    "preparation_bundles",
    "bundle_versions",
    "bundle_approvals",
    "interview_sources",
    "study_packages",
    "study_package_versions",
    "questions",
    "answer_attempts",
    "answer_feedback",
    "review_items",
    "interview_reviews",
    "tasks",
    "offers",
    "offer_events",
    "feedback_reports",
    "model_consents",
}


def csv_safe(value: str) -> str:
    return (
        "'" + value if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else value
    )


async def export(ctx: Context) -> None:
    async with Session() as db:
        await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
        pending = await db.scalar(
            select(DeletionRequest).where(
                DeletionRequest.owner_id == ctx.run.owner_id, DeletionRequest.status != "succeeded"
            )
        )
        if pending:
            raise DomainError("deletion_in_progress", "资料清理中，导出暂缓")
        request = await db.get(
            ExportRequest, UUID(str(ctx.run.inputs["export_id"])), with_for_update=True
        )
        if request is None or request.owner_id != ctx.run.owner_id:
            raise DomainError("not_found", "导出请求不存在", 404)
        output: dict[str, JsonValue] = {
            "format_version": "offerpilot-export-v1",
            "generated_at": now().isoformat(),
        }
        for table_name in sorted(EXPORT_TABLES):
            table = Base.metadata.tables.get(table_name)
            if table is None:
                continue
            rows = (
                (await db.execute(select(table).where(table.c.owner_id == ctx.run.owner_id)))
                .mappings()
                .all()
            )
            output[table_name] = [
                TypeAdapter(dict[str, JsonValue]).validate_python(
                    jsonable_encoder(dict(row), custom_encoder={Decimal: str})
                )
                for row in rows
            ]
        if request.format == "json":
            request.payload = output
        else:
            from offerpilot.modules.jobs.models import Job, JobVersion
            from offerpilot.modules.jobs.schemas import JobExtraction

            job_rows = await db.scalars(
                select(JobVersion)
                .join(Job, Job.current_version_id == JobVersion.id)
                .where(JobVersion.owner_id == ctx.run.owner_id)
            )
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow(["title", "company", "cities", "salary_raw", "text", "url"])
            for row in job_rows:
                job = JobExtraction.model_validate(row.data)
                from offerpilot.modules.jobs.models import TextSnapshot

                snapshot = await db.get(TextSnapshot, row.snapshot_id) if row.snapshot_id else None
                writer.writerow(
                    [
                        csv_safe(v)
                        for v in [
                            job.title,
                            job.company,
                            " / ".join(job.cities),
                            job.salary.raw,
                            snapshot.text or "" if snapshot else "",
                            snapshot.url or "" if snapshot else "",
                        ]
                    ]
                )
            request.csv_text = stream.getvalue()
        request.status, request.expires_at = (
            "succeeded",
            now() + timedelta(hours=settings().export_retention_hours),
        )
        await ctx.publish(db, {"export_id": str(request.id)})


async def maintenance() -> None:
    async with Session() as db:
        await db.execute(
            update(ExportRequest)
            .where(ExportRequest.expires_at <= now())
            .values(status="expired", payload=None, csv_text=None)
        )
        from offerpilot.modules.identity.models import LoginFailure
        from sqlalchemy import delete

        await db.execute(
            delete(LoginFailure).where(LoginFailure.created_at < now() - timedelta(days=1))
        )
        from offerpilot.modules.discovery.models import SourcePolicy
        from offerpilot.modules.operations.retention import tighten_retention

        policies = await db.scalars(
            select(SourcePolicy).where(
                (SourcePolicy.mode != "extract_allowed") | SourcePolicy.store_text.is_(False)
            )
        )
        for policy in policies:
            await tighten_retention(db, policy)
        await db.commit()
