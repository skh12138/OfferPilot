import re

from offerpilot.api.errors import DomainError
from offerpilot.modules.preparation.schemas import BundlePayload
from offerpilot.modules.profiles.schemas import Fact


def validate_claims(payload: BundlePayload, facts: list[Fact]) -> None:
    """Conservative P0 boundary: a claim must be a verbatim span of its cited confirmed fact.

    This deliberately trades paraphrasing freedom for an auditable baseline. User review still
    applies; a valid ID alone never authorizes an unrelated or stronger claim.
    """
    if re.search(
        r"完全符合|完全满足|百分之百符合",
        payload.introduction + payload.contact_draft + " ".join(c.text for c in payload.claims),
    ):
        raise DomainError("unsupported_qualification", "不能声明完全符合全部岗位条件", 422)
    allowed = {f.fact_id: f for f in facts}
    for claim in payload.claims:
        if any(f not in allowed for f in claim.fact_ids):
            raise DomainError("invalid_fact_reference", "引用包含未确认、撤回或其他版本的事实", 422)
        texts = [allowed[f].text for f in claim.fact_ids]
        if not any(claim.text in text for text in texts):
            raise DomainError("unsupported_claim", "自述超出已确认事实原文，请修改后审核", 422)
        if any(not any(quote in text for text in texts) for quote in claim.quotes):
            raise DomainError("invalid_quote", "引用片段不受事实支持", 422)
    # Free-form outlines may not become an alternate uncited autobiography.
    for text in [payload.introduction, payload.contact_draft]:
        if re.search(r"我(?:曾|在|负责|主导|完成|实现)|提升\d|降低\d", text):
            raise DomainError(
                "uncited_autobiography", "自由草稿不得包含无引用的个人经历，请放入 claims", 422
            )
    for task in payload.tasks:
        if any(f not in allowed for f in task.fact_ids):
            raise DomainError("invalid_fact_reference", "任务引用不可用事实", 422)
