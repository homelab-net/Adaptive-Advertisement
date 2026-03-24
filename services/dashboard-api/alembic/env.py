"""
Alembic environment — async SQLAlchemy (asyncpg).

Run migrations:
    cd services/dashboard-api
    alembic upgrade head

The DB URL is read from the DASHBOARD_DATABASE_URL environment variable,
falling back to the value in alembic.ini.
"""
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Import ORM models so Alembic's autogenerate can see the full metadata
from dashboard_api.models import Base  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override URL from environment
_db_url = os.environ.get(
    "DASHBOARD_DATABASE_URL",
    config.get_main_option("sqlalchemy.url"),
)


def run_migrations_offline() -> None:
    context.configure(
        url=_db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_db_url, echo=False)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
