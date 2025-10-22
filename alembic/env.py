import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from alembic import context

from sync_airbnb.models.base import Base

# Import all models so they are registered with Base.metadata
from sync_airbnb.models import chart_query, chart_summary, list_of_metrics, account  # noqa: F401

# Load .env before anything else
load_dotenv()

# --- Alembic config setup ---
config = context.config
fileConfig(config.config_file_name)

# Set DB URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Missing DATABASE_URL in .env")

config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Use Base.metadata which includes all registered models
target_metadata = Base.metadata

# --- Migration run modes ---


def run_migrations_offline():
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="alembic_airbnb_sync",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table="alembic_airbnb_sync",
        )
        with context.begin_transaction():
            context.run_migrations()


# --- Dispatch ---
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
