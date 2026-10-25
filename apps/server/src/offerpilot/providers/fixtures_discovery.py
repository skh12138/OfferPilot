"""Small synthetic public-information organizer used only by the demo/test provider."""

from pydantic import JsonValue


def organize_fixture(inputs: dict[str, JsonValue]) -> dict[str, JsonValue]:
    candidates = inputs.get("candidates", [])
    output: list[JsonValue] = []
    for row in candidates if isinstance(candidates, list) else []:
        if not isinstance(row, dict):
            continue
        evidence = str(row.get("evidence", ""))
        positions: list[JsonValue] = []
        if "Python" in evidence and "合成星河科技" in evidence:
            title = (
                "Python 应用开发实习"
                if "Python 应用开发实习" in evidence
                else "Python应用开发实习生"
            )
            positions.append(
                {
                    "title": title,
                    "company": "合成星河科技",
                    "cities": ["杭州"],
                    "education": "本科及以上" if "本科及以上" in evidence else None,
                    "requirements": [
                        s
                        for s in ["Python", "SQL", "API", "每周至少3天", "持续3个月"]
                        if s in evidence
                    ],
                    "responsibilities": ["处理异常和任务状态"]
                    if "处理异常和任务状态" in evidence
                    else [],
                    "salary": "200-300 CNY" if "200-300 CNY" in evidence else None,
                    "relevance": "high",
                    "relevance_reason": "岗位包含开发与实习要求，地点杭州。",
                    "difficulty": {
                        "level": "medium",
                        "reason": "合成预测：需具备Python与接口基础；不代表真实录用概率。",
                        "preparation": ["复习HTTP与SQL基础", "练习接口异常处理"],
                    },
                }
            )
        output.append(
            {
                "candidate_id": row["candidate_id"],
                "kind": "position" if positions else "unclear",
                "opportunities": positions,
                "note": "显式合成AI整理",
            }
        )
    return {"items": output}
