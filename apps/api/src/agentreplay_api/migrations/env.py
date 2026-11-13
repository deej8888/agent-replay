from alembic import context
from sqlalchemy import Connection

from agentreplay_api.database import Base, make_engine

config = context.config
connection = config.attributes.get("connection")


def migrate(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    import os

    context.configure(
        url=os.getenv("AGENTREPLAY_DATABASE_URL", "sqlite:///./agentreplay.db"),
        target_metadata=Base.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
elif connection is not None:
    migrate(connection)
else:
    with make_engine().connect() as connection:
        migrate(connection)
