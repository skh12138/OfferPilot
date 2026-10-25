import re
from datetime import date, timedelta

from offerpilot.api.errors import DomainError
from offerpilot.modules.interview.schemas import StudyPayload
from offerpilot.modules.jobs.schemas import JobExtraction
from offerpilot.modules.profiles.schemas import Fact


def next_review(today: date, mastery: str) -> date:
    return today + timedelta(
        days={"new": 1, "needs_review": 1, "practicing": 3, "confident": 7}[mastery]
    )


def validate_questions(
    payload: StudyPayload, job: JobExtraction, facts: list[Fact], sources: dict[str, str]
) -> None:
    fact_ids = {f.fact_id for f in facts}
    req_ids = {r.requirement_id for r in job.requirements}
    seen = set()
    for question in payload.questions:
        normalized = re.sub(r"\W+", "", question.prompt).casefold()
        if normalized in seen:
            raise DomainError("duplicate_question", "题目主题重复", 422)
        seen.add(normalized)
        if any(f not in fact_ids for f in question.fact_ids):
            raise DomainError("invalid_fact_reference", "题目引用不可用事实", 422)
        if any(r not in req_ids for r in question.requirement_ids):
            raise DomainError("invalid_requirement", "题目要求不属于当前 JD", 422)
        if question.source_kind == "experience_reported" and not question.source_refs:
            raise DomainError("unsupported_experience", "面经题缺少正文引用", 422)
        if question.source_kind == "experience_reported" and not any(
            question.prompt in sources.get(str(ref.source_id), "") for ref in question.source_refs
        ):
            raise DomainError(
                "adapted_question_requires_label", "改编题必须标为目标生成，不能伪装成原面经题", 422
            )
        for ref in [*question.source_refs, *question.inspired_by]:
            if ref.quote not in sources.get(str(ref.source_id), ""):
                raise DomainError("invalid_source_reference", "面经引用无已读原文支持", 422)
        personal = question.kind == "project" or bool(
            re.search(r"你(?:的项目|已完成|负责|主导|参与)", question.prompt)
        )
        hypothetical = bool(re.search(r"如果|假设|设想|是否", question.prompt))
        if personal and not hypothetical:
            cited = " ".join(f.text for f in facts if f.fact_id in question.fact_ids)
            if not question.fact_ids:
                raise DomainError(
                    "personal_question_without_fact", "题目不能假定未确认的个人经历", 422
                )
            for strength in ["主导", "独立完成", "独立负责", "带领", "生产环境", "商业化"]:
                if strength in question.prompt and strength not in cited:
                    raise DomainError("inflated_question", "题目夸大个人角色或完成范围", 422)
            for number in re.findall(r"\d+(?:\.\d+)?%?", question.prompt):
                if number not in cited:
                    raise DomainError("invented_question_metric", "个人题目包含无依据数字", 422)
        if question.kind == "project" and not question.fact_ids:
            raise DomainError("project_without_fact", "个人项目题须有已确认事实", 422)
        if not question.recommendation_reason.strip():
            raise DomainError("missing_reason", "缺少推荐依据", 422)
