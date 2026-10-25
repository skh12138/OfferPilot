import re
from datetime import date
from typing import Literal

from dateutil.relativedelta import relativedelta
from offerpilot.modules.jobs.schemas import Check, JobExtraction
from offerpilot.modules.profiles.schemas import Preferences

RULE_VERSION = "eligibility-v1"
EDUCATION = {"secondary": 1, "associate": 2, "bachelor": 3, "master": 4, "doctor": 5}


def calendar_months(start: date, months: int) -> date:
    return start + relativedelta(months=months)


def skill_tokens(text: str) -> set[str]:
    return {
        s.lower()
        for s in re.findall(
            r"(?<!\w)(?:JavaScript|Java|Python|PyTorch|TypeScript|Vue3?|SQL|FastAPI)(?!\w)",
            text,
            re.I,
        )
    }


def check_eligibility(
    profile: Preferences | None, job: JobExtraction
) -> tuple[Literal["pass", "fail", "unknown"], list[Check]]:
    """Only confirmed, explicit hard conditions can fail; missing is never unrestricted."""
    checks: list[Check] = []
    keys: list[
        Literal[
            "days_per_week",
            "duration_months",
            "graduation_year",
            "cities",
            "work_mode",
            "education",
        ]
    ] = [
        "days_per_week",
        "duration_months",
        "graduation_year",
        "cities",
        "work_mode",
        "education",
    ]
    for key in keys:
        condition = job.conditions.get(key)
        status: Literal["pass", "fail", "unknown"] = "unknown"
        reason = "岗位未明确或尚未校对该条件"
        evidence = condition.evidence.quote if condition and condition.evidence else None
        if condition and condition.review_status == "confirmed":
            if condition.strength != "hard":
                status, reason = "pass", "偏好或可协商项，不构成硬性淘汰"
            elif condition.unrestricted:
                status, reason = "pass", "原文明确不限"
            elif profile is None:
                reason = "未提供个人资料，待核实"
            else:
                actual = getattr(profile, key, None)
                value = condition.value
                if actual is None or actual == [] or value is None:
                    reason = "个人资料或岗位值缺失"
                elif (
                    key in {"days_per_week", "duration_months"}
                    and isinstance(value, int)
                    and isinstance(actual, int)
                ):
                    if key == "duration_months" and condition.unit != "calendar_month":
                        reason = "持续时间单位不明确"
                    else:
                        status = "pass" if actual >= value else "fail"
                        reason = f"可提供 {actual}，岗位至少要求 {value}"
                elif (
                    key == "education"
                    and isinstance(value, str)
                    and isinstance(actual, str)
                    and value in EDUCATION
                ):
                    status = "pass" if EDUCATION.get(actual, 0) >= EDUCATION[value] else "fail"
                    reason = f"学历 {actual}，最低要求 {value}"
                elif key == "graduation_year" and isinstance(value, list):
                    status = "pass" if str(actual) in value else "fail"
                    reason = f"毕业年份 {actual}，要求 {', '.join(value)}"
                elif key == "cities" and isinstance(value, list) and isinstance(actual, list):
                    status = "pass" if set(actual) & set(value) else "fail"
                    reason = f"可到岗城市 {actual}，岗位城市 {value}"
                elif key == "work_mode" and not profile.work_mode_is_hard:
                    status, reason = "pass", "个人办公方式为偏好，不形成硬性淘汰"
                elif key == "work_mode" and isinstance(value, str):
                    status = "pass" if actual == value else "fail"
                    reason = f"办公方式偏好 {actual}，要求 {value}"
        checks.append(Check(key=key, status=status, reason=reason, evidence=evidence))
    overall: Literal["pass", "fail", "unknown"] = (
        "fail"
        if any(c.status == "fail" for c in checks)
        else "unknown"
        if any(c.status == "unknown" for c in checks)
        else "pass"
    )
    return overall, checks


def verify(job: JobExtraction, text: str, today: date) -> tuple[str, str, list[str]]:
    availability, risk, evidence = "unknown", "no_known_flags", []
    if job.deadline and job.deadline < today:
        availability = "expired"
        evidence.append(f"明确截止日期 {job.deadline}")
    elif re.search(r"(职位已关闭|岗位已下线|停止招聘|招聘已结束)", text):
        availability = "closed"
        evidence.append("原文包含明确关闭表达")
    elif re.search(r"(正在招聘|开放申请|接受申请)", text):
        availability = "page_open"
        evidence.append("原文声明开放，不能保证仍有名额")
    if re.search(r"(请先支付|必须缴纳|收取押金|办理培训贷|保证录用)", text):
        risk = "high_risk_flag"
        evidence.append("存在预付款或保证录用表达，需人工复核")
    if job.conflicts:
        risk = "needs_review"
        evidence.extend(job.conflicts)
    return availability, risk, evidence
