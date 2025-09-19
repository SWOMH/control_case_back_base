import asyncio
from logging.config import fileConfig
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from database.models.users import *
from database.models.support import *
from database.models.balance import *
from database.models.court import *
from database.models.documents import *
from database.models.documents_app import *
from database.models.notifications import *
from database.models.agreement import *
from database.models.schedule import *
from database.models.news_feed import *
from config.constants import DEV_CONSTANT
from database.base import Base

config = context.config
config.set_main_option('sqlalchemy.url', DEV_CONSTANT.url_connection)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    """Асинхронное выполнение миграций"""
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online():
    """Запуск асинхронных миграций с обработкой event loop"""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # Если event loop уже запущен (например, в async среде)
        task = loop.create_task(run_async_migrations())
        task.add_done_callback(lambda t: loop.stop())
        loop.run_forever()
    else:
        # Если event loop не запущен
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()