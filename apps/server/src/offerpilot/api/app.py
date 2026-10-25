from fastapi import FastAPI
from offerpilot.api.errors import install_errors
from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import Session
from offerpilot.modules.applications.router import router as applications_router
from offerpilot.modules.control.router import router as control_router
from offerpilot.modules.discovery.router import router as discovery_router
from offerpilot.modules.identity.router import router as identity_router
from offerpilot.modules.interview.practice_router import router as practice_router
from offerpilot.modules.interview.review_router import router as review_router
from offerpilot.modules.interview.router import router as interview_router
from offerpilot.modules.jobs.duplicates import router as duplicates_router
from offerpilot.modules.jobs.router import router as jobs_router
from offerpilot.modules.offers.router import router as offers_router
from offerpilot.modules.operations.router import router as operations_router
from offerpilot.modules.preparation.router import router as preparation_router
from offerpilot.modules.profiles.router import router as profiles_router
from offerpilot.modules.runs.router import router as runs_router
from offerpilot.modules.tasks.router import router as tasks_router
from pydantic import BaseModel
from sqlalchemy import text

app = FastAPI(title="OfferPilot", version="0.1.0")
install_errors(app)


class Health(BaseModel):
    status: str


class Capabilities(BaseModel):
    mode: str
    model_available: bool
    search_available: bool
    model: str
    max_compare: int = 4
    max_text: int = 50000


@app.get("/api/v1/health/live", response_model=Health)
async def live() -> Health:
    return Health(status="ok")


@app.get("/api/v1/health/ready", response_model=Health)
async def ready() -> Health:
    async with Session() as db:
        version = await db.scalar(text("SELECT version_num FROM alembic_version"))
        if version != "0010":
            from offerpilot.api.errors import DomainError

            raise DomainError("migration_required", "数据库需要迁移到当前版本", 503)
    return Health(status="ready")


@app.get("/api/v1/capabilities", response_model=Capabilities)
async def capabilities() -> Capabilities:
    cfg = settings()
    return Capabilities(
        mode=cfg.app_mode,
        model_available=cfg.app_mode != "live" or bool(cfg.deepseek_api_key.get_secret_value()),
        search_available=cfg.app_mode != "live" or bool(cfg.tavily_api_key.get_secret_value()),
        model=cfg.llm_model,
    )


for router in [
    identity_router,
    profiles_router,
    jobs_router,
    runs_router,
    discovery_router,
    duplicates_router,
    applications_router,
    tasks_router,
    preparation_router,
    interview_router,
    practice_router,
    review_router,
    offers_router,
    operations_router,
    control_router,
]:
    app.include_router(router, prefix="/api/v1")
