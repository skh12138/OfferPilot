"""Explicit synthetic provider. Imported only in demo/test modes."""

import re
from uuid import uuid4

from offerpilot.modules.jobs.rules import skill_tokens
from offerpilot.providers.base import ContentResult, Generated, SearchHit, SearchResult, Usage
from pydantic import JsonValue

DEMO_TEXT = """合成星河科技｜Python 应用开发实习
城市：杭州
每周至少3天，持续3个月，本科及以上，2027届。
职责：使用 Python 开发 API，处理异常和任务状态。
要求：Python、SQL、API；JavaScript 优先。
日薪 200-300 CNY，正在招聘，本招聘不收取培训费。"""


class FixtureProvider:
    async def search(self, query: str, max_results: int = 8) -> SearchResult:
        if "面经" in query:
            return SearchResult(results=[])
        return SearchResult(
            results=[
                SearchHit(
                    url="https://synthetic.example/jobs/python-1",
                    title="合成星河科技 Python 应用开发实习",
                    content="合成星河科技招聘Python应用开发实习生，杭州；本科及以上；每周至少3天，持续3个月；Python、SQL、API。合成搜索摘要，不是正文。",
                )
            ][:max_results]
        )

    async def extract(self, urls: list[str]) -> ContentResult:
        return ContentResult(texts={url: DEMO_TEXT for url in urls}, failures={})

    async def generate_json(
        self,
        task: str,
        schema: dict[str, JsonValue],
        inputs: dict[str, JsonValue],
        max_tokens: int = 4096,
    ) -> Generated:
        text = str(inputs.get("text", ""))
        if task == "resume_parse":
            facts: list[JsonValue] = []
            for i, line in enumerate(text.splitlines()):
                if (
                    line.strip()
                    and "[联系方式已隐藏]" not in line
                    and not re.search(r"@|1[3-9]\d{9}", line)
                ):
                    facts.append(
                        {
                            "fact_id": str(uuid4()),
                            "text": line,
                            "status": "unconfirmed",
                            "evidence": {
                                "paragraph_id": f"p{i + 1}",
                                "quote": line,
                                "source_kind": "resume_text",
                            },
                        }
                    )
            data: dict[str, JsonValue] = {"facts": facts}
        elif task == "job_normalize":
            lines = text.splitlines()
            conditions: dict[str, JsonValue] = {}
            for key, pattern, unit in [
                ("days_per_week", r"(?:每周至少|每周)(\d)天", None),
                ("duration_months", r"持续(\d+)个月", "calendar_month"),
            ]:
                for i, line in enumerate(lines):
                    found = re.search(pattern, line)
                    if found:
                        conditions[key] = {
                            "value": int(found.group(1)),
                            "unit": unit,
                            "review_status": "unreviewed",
                            "evidence_status": "supported",
                            "evidence": {
                                "paragraph_id": f"p{i + 1}",
                                "quote": line,
                                "source_kind": "user_provided",
                            },
                        }
            for i, line in enumerate(lines):
                evidence: dict[str, JsonValue] = {
                    "paragraph_id": f"p{i + 1}",
                    "quote": line,
                    "source_kind": "user_provided",
                }
                strength = (
                    "negotiable" if "可协商" in line else "preferred" if "优先" in line else "hard"
                )
                for key in ["days_per_week", "duration_months"]:
                    current_condition = conditions.get(key)
                    if isinstance(current_condition, dict):
                        current_condition["strength"] = strength
                for phrase, key in [
                    ("每周天数不限", "days_per_week"),
                    ("毕业届别不限", "graduation_year"),
                ]:
                    if phrase in line:
                        conditions[key] = {
                            "unrestricted": True,
                            "review_status": "unreviewed",
                            "evidence_status": "supported",
                            "evidence": evidence,
                        }
                years = re.findall(r"(20\d{2})届", line)
                if years:
                    conditions["graduation_year"] = {
                        "value": list(years),
                        "review_status": "unreviewed",
                        "evidence_status": "supported",
                        "evidence": evidence,
                    }
                for phrase, value in [("本科", "bachelor"), ("硕士", "master"), ("博士", "doctor")]:
                    if phrase in line:
                        conditions["education"] = {
                            "value": value,
                            "review_status": "unreviewed",
                            "evidence_status": "supported",
                            "evidence": evidence,
                        }
            data = {
                "classification": "job_list"
                if "招聘目录" in text
                else "non_job"
                if "课程广告" in text
                else "job_detail",
                "title": lines[0] if lines else "合成岗位",
                "company": "合成星河科技",
                "cities": [c for c in ["杭州", "上海", "北京"] if c in text],
                "conditions": conditions,
                "requirements": [
                    {
                        "requirement_id": str(uuid4()),
                        "text": line,
                        "skills": list(sorted(skill_tokens(line))),
                    }
                    for line in lines
                    if "要求" in line or "职责" in line
                ],
                "missing_fields": ["department", "deadline"],
            }
        elif task == "search_organize":
            from offerpilot.providers.fixtures_discovery import organize_fixture

            data = organize_fixture(inputs)
        elif task == "search_parse":
            data = {
                "keywords": re.sub(r"\S+@\S+|1[3-9]\d{9}", "", text),
                "cities": [c for c in ["杭州", "上海", "北京"] if c in text],
                "confirmed": False,
            }
        elif task == "material_prepare":
            raw_facts = inputs.get("facts", [])
            usable = (
                [f for f in raw_facts if isinstance(f, dict)] if isinstance(raw_facts, list) else []
            )
            data = {
                "claims": [
                    {
                        "text": str(f["text"]),
                        "fact_ids": [str(f["fact_id"])],
                        "quotes": [str(f["text"])],
                    }
                    for f in usable[:3]
                ],
                "gaps": ["请核实岗位未注明的到岗条件"],
                "tasks": [
                    {
                        "title": "核实岗位条件",
                        "reason": "JD 有信息缺口",
                        "deliverable": "一份条件确认记录",
                        "acceptance": "记录来源与确认结果",
                        "priority": "normal",
                        "requirement_ids": [],
                        "fact_ids": [],
                    }
                ],
                "introduction": "请结合下列已确认事实组织自我介绍；缺失信息由本人补充。",
                "contact_draft": "您好，我希望了解该岗位的到岗要求。",
            }
        elif task == "study_prepare":
            raw_job = inputs.get("job", {})
            job = raw_job if isinstance(raw_job, dict) else {}
            reqs = job.get("requirements", [])
            req_ids = (
                [str(r["requirement_id"]) for r in reqs if isinstance(r, dict)]
                if isinstance(reqs, list)
                else []
            )
            topics = [
                "接口设计",
                "异常处理",
                "数据一致性",
                "测试",
                "任务恢复",
                "SQL",
                "安全边界",
                "工程取舍",
                "沟通",
                "反问",
                "复盘",
                "调试",
                "性能",
                "日志",
                "协作",
            ]
            n = int(str(inputs.get("count", 8)))
            data = {
                "topics": [
                    {
                        "topic": "岗位工程能力",
                        "reason": "来自当前 JD，未找到可读面经",
                        "requirement_ids": list(req_ids),
                    }
                ],
                "limitations": ["合成演示；没有可读面经，题目为目标岗位模拟题。"],
                "questions": [
                    {
                        "topic": topic,
                        "kind": "technical",
                        "difficulty": "medium",
                        "prompt": f"围绕目标岗位，请说明{topic}的设计、失败边界与验证方法。",
                        "recommendation_reason": f"当前 JD 的工程要求需要理解{topic}，不假定你已做过。",
                        "requirement_ids": list(req_ids),
                        "fact_ids": [],
                        "source_kind": "generated_for_target",
                        "source_refs": [],
                        "rubric": ["说明前提", "覆盖失败路径", "给出验证依据"],
                        "hints": ["从一个具体失败场景开始"],
                        "answer_guidance": "按背景、方案、边界、验证组织；未知结论待核实。",
                        "follow_ups": ["如何验证？"],
                        "quality_flags": ["知识答案待核实"],
                    }
                    for topic in topics[:n]
                ],
            }
        elif task == "feedback":
            data = {
                "strengths": ["已提交可回看的回答"],
                "issues": ["请补充失败路径和验证依据"],
                "suggested_revision_outline": ["问题背景", "选择与取舍", "失败边界", "验证方法"],
                "follow_up_question": "如果请求超时，你会如何确认真实执行结果？",
                "topic_observations": ["建议次日复习"],
                "uncertainties": ["合成反馈，非招聘结论"],
                "levels": {
                    "correctness": "待核实",
                    "completeness": "可补充",
                    "structure": "可补充",
                    "evidence": "待补充",
                    "relevance": "相关",
                },
                "fact_ids": [],
            }
        else:
            raise ValueError(f"Unsupported fixture task: {task}")
        return Generated(
            data=data,
            usage=Usage(input_tokens=0, output_tokens=0, response_model="fixture-synthetic-v1"),
        )
