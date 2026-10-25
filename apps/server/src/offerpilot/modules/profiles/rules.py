from offerpilot.modules.jobs.rules import skill_tokens
from offerpilot.modules.jobs.schemas import JobExtraction
from offerpilot.modules.profiles.schemas import Fact


def relevant_facts(facts: list[Fact], job: JobExtraction | None, limit: int = 12) -> list[Fact]:
    """Small deterministic lexical baseline, restricted to the supplied confirmed fact set."""
    required = {skill.lower() for r in job.requirements for skill in r.skills} if job else set()
    return sorted(facts, key=lambda f: (-len(skill_tokens(f.text) & required), str(f.fact_id)))[
        :limit
    ]
