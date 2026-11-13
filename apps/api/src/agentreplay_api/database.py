import os
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    started_at: Mapped[Any] = mapped_column(DateTime(timezone=True), index=True)
    duration_ms: Mapped[float] = mapped_column(Float)
    mode: Mapped[str] = mapped_column(String(20))
    model: Mapped[str | None] = mapped_column(String(200), index=True)
    source_run_id: Mapped[str | None] = mapped_column(String(36))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (Index("ix_runs_started_id", "started_at", "id"),)


class SpanRow(Base):
    __tablename__ = "spans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(36))
    sequence: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


def make_engine(url: str | None = None) -> Engine:
    url = url or os.getenv("AGENTREPLAY_DATABASE_URL") or "sqlite:///./agentreplay.db"
    options: dict[str, Any] = {}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            options["poolclass"] = StaticPool
    engine = create_engine(url, **options)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def configure_sqlite(connection: Any, _: Any) -> None:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")

    return engine


def make_sessions(engine: Engine) -> sessionmaker[Any]:
    return sessionmaker(engine, expire_on_commit=False)
