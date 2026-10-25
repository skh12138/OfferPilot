from typing import TypedDict
from uuid import UUID

import httpx
from langgraph.graph import END, START, StateGraph
from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import Session
from offerpilot.modules.runs.models import AgentRun
from offerpilot.providers.base import ContentProvider, LLMProvider, SearchProvider
from offerpilot.providers.deepseek import DeepSeekLLMProvider
from offerpilot.providers.fixtures import FixtureProvider
from offerpilot.providers.tavily import TavilyContentProvider, TavilySearchProvider
from offerpilot.worker.context import Context
from offerpilot.worker.queue import guarded
from offerpilot.workflows.parsing import job_import, resume_parse


class State(TypedDict):
    run_id: str


async def execute(run_id: UUID, token: UUID) -> None:
    async with Session() as db:
        run = await db.get(AgentRun, run_id)
        if run is None:
            return
    ctx = Context(run, token)
    async with httpx.AsyncClient(follow_redirects=False) as client:
        cfg = settings()
        llm: LLMProvider
        search: SearchProvider
        content: ContentProvider
        if cfg.app_mode in {"demo", "test"}:
            llm, search, content = FixtureProvider(), FixtureProvider(), FixtureProvider()
        else:
            llm = DeepSeekLLMProvider(client, cfg.deepseek_api_key.get_secret_value(), run.model)
            search = TavilySearchProvider(
                client, cfg.tavily_api_key.get_secret_value(), detailed=run.kind == "search"
            )
            content = TavilyContentProvider(client, cfg.tavily_api_key.get_secret_value())

        async def validate(state: State) -> State:
            async with Session() as db:
                await guarded(db, run.owner_id, run.id, token)
            return state

        async def process(state: State) -> State:
            if run.kind == "resume_parse":
                await resume_parse(ctx, llm)
            elif run.kind == "job_import":
                await job_import(ctx, llm)
            else:
                from offerpilot.workflows.dispatch import dispatch

                await dispatch(ctx, llm, search, content)
            return state

        graph = StateGraph(State)
        graph.add_node("validate_inputs", validate)
        graph.add_node(run.kind, process)
        graph.add_edge(START, "validate_inputs")
        graph.add_edge("validate_inputs", run.kind)
        graph.add_edge(run.kind, END)
        await graph.compile().ainvoke({"run_id": str(run_id)})
