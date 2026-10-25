from offerpilot.infrastructure.db import Base
from sqlalchemy import CheckConstraint

STATE_CONSTRAINTS: list[tuple[str, str, list[str]]] = [
    ("agent_runs", "status", ["queued", "running", "succeeded", "partial", "failed", "cancelled"]),
    (
        "applications",
        "stage",
        ["interested", "preparing", "submitted", "assessment", "offer", "onboarding", "closed"],
    ),
    (
        "assessment_rounds",
        "status",
        [
            "pending",
            "scheduled",
            "completed_waiting_result",
            "passed",
            "failed",
            "cancelled",
            "skipped",
        ],
    ),
    ("tasks", "status", ["todo", "in_progress", "waiting_external", "done", "cancelled"]),
    ("offers", "type", ["oral", "written"]),
    (
        "offers",
        "decision",
        ["undecided", "negotiating", "accepted", "declined", "expired", "withdrawn"],
    ),
    ("review_items", "mastery", ["new", "needs_review", "practicing", "confident"]),
    ("source_policies", "mode", ["metadata_only", "extract_allowed", "disabled"]),
    ("source_policies", "purpose", ["jobs", "interview", "knowledge"]),
    ("provider_calls", "status", ["reserved", "unknown", "completed", "failed"]),
    ("job_preferences", "preference", ["interested", "priority", "paused", "excluded"]),
]


def install_constraints() -> None:
    for table, column, values in STATE_CONSTRAINTS:
        expression = column + " IN (" + ",".join("'" + v + "'" for v in values) + ")"
        Base.metadata.tables[table].append_constraint(
            CheckConstraint(expression, name=column + "_values")
        )
