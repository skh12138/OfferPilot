import re
from urllib.parse import urlsplit

from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.config import settings
from offerpilot.modules.discovery.models import SourcePolicy
from offerpilot.modules.discovery.schemas import SpecInput
from offerpilot.providers.urls import canonical_url
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def search_queries(spec: SpecInput) -> list[str]:
    # Expansion appends synonyms only. User hard conditions remain verbatim in every query.
    if re.search(r"@|1[3-9]\d{9}", spec.keywords):
        raise DomainError("private_search_terms", "请移除邮箱、手机号等身份信息", 422)
    base = " ".join(
        [
            spec.keywords,
            *spec.cities,
            {
                "internship": "实习生",
                "graduate": "校招 应届生",
                "experienced": "社会招聘",
                "unknown": "招聘",
            }[spec.employment_type],
            f"每周{spec.days_per_week}天" if spec.days_per_week else "",
        ]
    )
    if "后端" in spec.keywords or "后台" in spec.keywords:
        directions = [" 服务端开发 招聘", " 后端工程师 职位要求"]
    elif "前端" in spec.keywords:
        directions = [" Web前端 招聘", " 前端工程师 职位要求"]
    elif "开发" in spec.keywords:
        directions = [" 后端开发 招聘", " 前端开发 招聘"]
    else:
        directions = [" 职位详情 招聘", " 实习 职位要求"]
    variants = [
        base + " 招聘 岗位职责 任职要求",
        base + directions[0],
        base + directions[1],
        base + " 软件工程 招聘详情",
        base + " 企业官网 招聘",
        base + " 职位申请 工作内容",
    ]
    return variants[: spec.max_queries]


def validate_public_query(text: str) -> None:
    if re.search(r"@|1[3-9]\d{9}", text):
        raise DomainError("private_search_terms", "搜索条件中请勿填写手机号、邮箱等个人资料", 422)


def preserve_scope(original: SpecInput, parsed: SpecInput) -> SpecInput:
    """Keep explicit human constraints even if the model suggests a wider search."""
    cities = [
        c
        for c in [
            "杭州",
            "上海",
            "北京",
            "深圳",
            "广州",
            "南京",
            "苏州",
            "成都",
            "武汉",
            "西安",
            "重庆",
            "宁波",
            "合肥",
            "长沙",
            "天津",
        ]
        if c in original.keywords
    ]
    parsed.cities = original.cities or cities or parsed.cities
    days = re.search(r"每周(?:至少|可|能)?\s*([1-7])\s*天", original.keywords)
    parsed.days_per_week = original.days_per_week or (
        int(days[1]) if days else parsed.days_per_week
    )
    if "实习" in original.keywords:
        parsed.employment_type = "internship"
    parsed.max_queries, parsed.max_results, parsed.max_extracts = (
        original.max_queries,
        original.max_results,
        original.max_extracts,
    )
    parsed.raw_keywords, parsed.confirmed, parsed.natural_language = original.keywords, True, False
    return parsed


async def allowed_source(db: AsyncSession, url: str, purpose: str) -> SourcePolicy | None:
    clean = canonical_url(url)
    host = urlsplit(clean).hostname
    if settings().app_mode in {"demo", "test"} and host == "synthetic.example":
        return SourcePolicy(
            domain="synthetic.example",
            purpose=purpose,
            mode="extract_allowed",
            store_text=True,
            store_excerpt=True,
            usage_basis="显式合成 fixture，不联网",
        )
    policy = await db.scalar(
        select(SourcePolicy).where(SourcePolicy.domain == host, SourcePolicy.purpose == purpose)
    )
    if policy and policy.mode == "disabled":
        return policy
    return policy


async def extraction_permission(db: AsyncSession, url: str, purpose: str) -> SourcePolicy | None:
    policy = await allowed_source(db, url, purpose)
    if not policy or policy.mode != "extract_allowed":
        return None
    return policy
