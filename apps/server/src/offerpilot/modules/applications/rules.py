from offerpilot.api.errors import DomainError

STAGES = ["interested", "preparing", "submitted", "assessment", "offer", "onboarding", "closed"]


def transition(
    current: str,
    target: str,
    event_type: str,
    reason: str,
    *,
    evidence: str | None = None,
    close_reason: str | None = None,
) -> None:
    if event_type in {"correction", "reopen"} and not reason.strip():
        raise DomainError("reason_required", "更正和重开必须说明原因", 422)
    if current == "closed" and event_type != "reopen":
        raise DomainError("application_closed", "已结束申请须先重开")
    if event_type == "reopen" and current != "closed":
        raise DomainError("not_closed", "只有已结束申请可以重开")
    if event_type not in {"correction", "reopen"} and STAGES.index(target) < STAGES.index(current):
        raise DomainError("correction_required", "回退须使用更正事件")
    if target == "closed" and not close_reason:
        raise DomainError("close_reason_required", "结束申请须说明原因", 422)
    required = {
        "submitted": "submission",
        "assessment": "round",
        "offer": "offer",
        "onboarding": "acceptance",
    }
    if target != current and target in required and evidence != required[target]:
        raise DomainError(
            "event_evidence_required", "该阶段需要实际投递、考核、Offer 或接受决定的对应记录"
        )
