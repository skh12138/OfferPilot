import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import Base
from offerpilot.infrastructure import models


def run_sync(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True, include_object=lambda obj, name, type_, reflected, compare_to: name != "deployment_metadata")
    with context.begin_transaction():
        context.run_migrations()


async def migrate():
    engine = create_async_engine(settings().database_url)
    async with engine.connect() as connection:
        await connection.run_sync(run_sync)
    await engine.dispose()


asyncio.run(migrate())
