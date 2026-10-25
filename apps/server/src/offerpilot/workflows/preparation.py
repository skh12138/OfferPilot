from uuid import UUID

from offerpilot.api.errors import DomainError
from offerpilot.api.schemas import digest
from offerpilot.infrastructure.db import Session
from offerpilot.infrastructure.owned import get_owned
from offerpilot.modules.applications.models import Application
from offerpilot.modules.jobs.models import JobVersion
from offerpilot.modules.jobs.schemas import JobExtraction
from offerpilot.modules.preparation.models import BundleVersion, PreparationBundle
from offerpilot.modules.preparation.rules import validate_claims
from offerpilot.modules.preparation.schemas import BundlePayload
from offerpilot.modules.profiles.service import confirmed_facts
from offerpilot.providers.base import LLMProvider
from offerpilot.worker.context import Context
from offerpilot.worker.queue import guarded
from pydantic import JsonValue


async def prepare(ctx: Context, llm: LLMProvider) -> None:
    async with Session() as db:
        if not ctx.run.application_id:
            raise DomainError("invalid_basis", "缺少申请")
        app = await get_owned(db, Application, ctx.run.owner_id, ctx.run.application_id)
        basis = int(str(ctx.run.inputs["basis_revision"]))
        if app.basis_revision != basis:
            raise DomainError("basis_changed", "准备基准已更新")
        facts = await confirmed_facts(db, app.owner_id, ctx.run.profile_version_id)
        job = (
            await get_owned(db, JobVersion, app.owner_id, app.job_version_id)
            if app.job_version_id
            else None
        )
        job_data = job.data if job else {}
        from offerpilot.modules.jobs.rules import check_eligibility
        from offerpilot.modules.profiles.rules import relevant_facts
        from offerpilot.modules.profiles.schemas import Preferences
        from offerpilot.modules.profiles.service import valid_profile

        data_job = JobExtraction.model_validate(job_data) if job_data else None
        facts = relevant_facts(facts, data_job)
        profile = (
            await valid_profile(db, app.owner_id, ctx.run.profile_version_id)
            if ctx.run.profile_version_id
            else None
        )
        outcome, checks = (
            check_eligibility(
                Preferences.model_validate(profile.preferences) if profile else None, data_job
            )
            if data_job
            else ("unknown", [])
        )
        round_context: dict[str, JsonValue] = {}
        if ctx.run.inputs.get("round_id"):
            from offerpilot.modules.applications.models import AssessmentRound

            rnd = await get_owned(
                db, AssessmentRound, app.owner_id, UUID(str(ctx.run.inputs["round_id"]))
            )
            if rnd.application_id != app.id:
                raise DomainError("invalid_parent", "考核与申请不一致", 404)
            round_context = {"name": rnd.name, "type": rnd.type}

    def validate(raw: dict[str, JsonValue]) -> None:
        payload = BundlePayload.model_validate(raw)
        validate_claims(payload, facts)
        requirements = (
            {r.requirement_id for r in JobExtraction.model_validate(job_data).requirements}
            if job_data
            else set()
        )
        if any(r not in requirements for t in payload.tasks for r in t.requirement_ids):
            raise DomainError("invalid_requirement", "任务引用不属于当前 JD")

    payload = await ctx.generate(
        "generate_tasks_and_claims",
        "material_prepare",
        BundlePayload,
        {
            "facts": [f.model_dump(mode="json") for f in facts],
            "job": job_data,
            "eligibility": {
                "overall": outcome,
                "checks": [c.model_dump(mode="json") for c in checks],
            },
            "round": round_context,
        },
        llm.generate_json,
        validate,
    )
    async with Session() as db:
        await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
        current = await get_owned(
            db, Application, ctx.run.owner_id, ctx.run.application_id, lock=True
        )
        if current.basis_revision != basis:
            raise DomainError("basis_changed", "生成时准备基准已改变")
        validate_claims(
            BundlePayload.model_validate(payload),
            await confirmed_facts(db, current.owner_id, ctx.run.profile_version_id),
        )
        bundle = PreparationBundle(owner_id=current.owner_id, application_id=current.id)
        db.add(bundle)
        await db.flush()
        version = BundleVersion(
            owner_id=current.owner_id,
            bundle_id=bundle.id,
            application_id=current.id,
            job_version_id=current.job_version_id,
            profile_version_id=ctx.run.profile_version_id,
            basis_revision=basis,
            round_id=UUID(str(ctx.run.inputs["round_id"]))
            if ctx.run.inputs.get("round_id")
            else None,
            data=payload,
            payload_hash=digest(payload),
            prompt_version=ctx.run.prompt_version,
            model=ctx.run.model,
            reason="生成草稿，待本人审核",
        )
        db.add(version)
        await db.flush()
        bundle.current_version_id = version.id
        await ctx.publish(db, {"bundle_id": str(bundle.id)})
