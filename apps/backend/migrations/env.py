"""Alembic configuration file."""

import asyncio
import os
from logging.config import fileConfig
from dotenv import load_dotenv

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from alembic import context

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Create Base directly here to avoid importing database.py with async engine creation
from sqlalchemy.orm import declarative_base
Base = declarative_base()

# Now we need to manually register all models
# Import models after Base is created
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import all model modules to register them with Base
from app.models.user import User
from app.models.project import Project
from app.models.board import Board
from app.models.base_node import BaseNode
from app.models.source_node import SourceNode
from app.models.content_node import ContentNode
from app.models.widget_node import WidgetNode
from app.models.comment_node import CommentNode
from app.models.edge import Edge
from app.models.project_widget import ProjectWidget
from app.models.project_table import ProjectTable
from app.models.dashboard import Dashboard
from app.models.dashboard_item import DashboardItem
from app.models.dashboard_share import DashboardShare

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = configuration.get("sqlalchemy.url", "")

    context.configure(
        url=configuration["sqlalchemy.url"],
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine and associate a connection with the context."""
    
    # Get DATABASE_URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    connectable = create_async_engine(
        database_url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
