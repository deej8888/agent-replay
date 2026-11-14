import hmac
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal
from uuid import UUID

from agentreplay import MemoryTransport, Redactor, ReplayDivergence, Run, Tracer, export_regression
from agentreplay.redaction import sanitize_run
from agentreplay_examples.agent import shopping_agent
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import Engine, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from .database import RunRow, SpanRow, make_engine, make_sessions
from .service import load_run, playback, reexecute, store_run


class BodyLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return
        data = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            data.extend(message.get("body", b""))
            if len(data) > 2_097_152:
                await JSONResponse({"detail": "Trace body exceeds 2 MiB"}, status_code=413)(
                    scope, receive, send
                )
                return
            if not message.get("more_body", False):
                break

        async def buffered_receive() -> Any:
            return {"type": "http.request", "body": bytes(data), "more_body": False}

        await self.app(scope, buffered_receive, send)


class DemoRequest(BaseModel):
    request: str = Field(
        default="Find a mechanical keyboard under $100", min_length=1, max_length=2000
    )
    fail: bool = False


class ReplayRequest(BaseModel):
    mode: Literal["playback", "reexecution"]
    simulate_divergence: bool = False


def create_app(engine: Engine | None = None, *, migrate: bool = True) -> FastAPI:
    engine = engine or make_engine()
    sessions = make_sessions(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if migrate:
            from pathlib import Path

            from alembic import command
            from alembic.config import Config

            config = Config()
            config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
            with engine.begin() as connection:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
        yield
        engine.dispose()

    app = FastAPI(title="AgentReplay API", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Never reflect raw captured credentials in validation error responses.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": list(e["loc"]), "msg": Redactor().text(e["msg"]), "type": e["type"]}
                    for e in exc.errors()
                ]
            },
        )

    app.add_middleware(BodyLimit)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv(
            "AGENTREPLAY_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(","),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    @app.middleware("http")
    async def authenticate(request: Request, call_next: Any) -> Any:
        key = os.getenv("AGENTREPLAY_API_KEY", "")
        if (
            key
            and request.url.path != "/health"
            and request.method != "OPTIONS"
            and not hmac.compare_digest(request.headers.get("X-API-Key", ""), key)
        ):
            return JSONResponse({"detail": "Invalid API key"}, status_code=401)
        return await call_next(request)

    def db_session() -> Iterator[Session]:
        with sessions() as db:
            yield db

    DB = Annotated[Session, Depends(db_session)]

    def get_run(db: Session, run_id: UUID) -> Run:
        run = load_run(db, str(run_id))
        if run is None:
            raise HTTPException(404, "Run not found")
        return run

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/runs", status_code=201, response_model=Run)
    def ingest(run: Run, db: DB) -> Run:
        # Sanitize on the server too; the SDK is not a trusted security boundary.
        run = sanitize_run(run)
        if len(run.model_dump_json().encode()) > 2_097_152:
            raise HTTPException(413, "Sanitized trace exceeds 2 MiB")
        try:
            return store_run(db, run)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, "Run or span ID already exists") from exc

    @app.get("/v1/runs")
    def list_runs(
        db: DB,
        q: str = Query(default="", max_length=200),
        status: Literal["success", "error"] | None = None,
        model: str | None = Query(default=None, max_length=200),
        mode: Literal["record", "playback", "reexecution"] | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> dict[str, Any]:
        statement = select(RunRow)
        if q:
            statement = statement.where(
                or_(
                    RunRow.name.icontains(q, autoescape=True),
                    RunRow.id.icontains(q, autoescape=True),
                )
            )
        if status:
            statement = statement.where(RunRow.status == status)
        if model:
            statement = statement.where(RunRow.model == model)
        if mode:
            statement = statement.where(RunRow.mode == mode)
        total = db.scalar(select(func.count()).select_from(statement.subquery()))
        rows = db.scalars(
            statement.order_by(RunRow.started_at.desc(), RunRow.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return {
            "items": [r.payload for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.get("/v1/runs/{run_id}", response_model=Run)
    def detail(run_id: UUID, db: DB) -> Run:
        return get_run(db, run_id)

    @app.get("/v1/runs/{run_id}/regression", response_class=Response)
    def regression_bundle(
        run_id: UUID, db: DB, entrypoint: str | None = Query(default=None, max_length=500)
    ) -> Response:
        source = get_run(db, run_id)
        # Legacy demo recordings predate automatic entrypoint capture.
        if (
            not entrypoint
            and not source.metadata.get("entrypoint")
            and source.metadata.get("replay_target") == "shopping-demo"
        ):
            entrypoint = "agentreplay_examples.agent:shopping_agent"
        try:
            bundle = export_regression(source, entrypoint)
        except (ValueError, ReplayDivergence) as exc:
            raise HTTPException(422, str(exc)) from exc
        return Response(
            content=bundle,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="agentreplay-regression-{run_id.hex[:12]}.zip"',
                "Cache-Control": "no-store",
            },
        )

    @app.get("/v1/runs/{run_id}/spans/{span_id}")
    def span_detail(run_id: UUID, span_id: UUID, db: DB) -> dict[str, Any]:
        row = db.get(SpanRow, str(span_id))
        if row is None or row.run_id != str(run_id):
            raise HTTPException(404, "Span not found")
        return row.payload

    @app.post("/v1/demo", response_model=Run, status_code=201)
    def demo(body: DemoRequest, db: DB) -> Run:
        transport = MemoryTransport()
        with Tracer(transport).use():
            try:
                shopping_agent(body.request, body.fail)
            except ValueError:
                pass
        return store_run(db, transport.runs[0])

    @app.post("/v1/runs/{run_id}/replays", response_model=Run, status_code=201)
    def replay_run(run_id: UUID, body: ReplayRequest, db: DB) -> Run:
        source = get_run(db, run_id)
        try:
            result = (
                playback(source)
                if body.mode == "playback"
                else reexecute(source, body.simulate_divergence)
            )
        except (ValueError, ReplayDivergence) as exc:
            raise HTTPException(422, str(exc)) from exc
        return store_run(db, result)

    @app.get("/v1/compare")
    def compare(left: UUID, right: UUID, db: DB) -> dict[str, Any]:
        a, b = get_run(db, left), get_run(db, right)
        changes = []

        # Align using semantic path plus sibling occurrence, not volatile span IDs.
        def keyed(run: Run) -> dict[str, Any]:
            paths: dict[UUID, str] = {}
            counts: dict[str, int] = {}
            result = {}
            for span in run.spans:
                base = f"{paths.get(span.parent_id, '') if span.parent_id else ''}/{span.kind}:{span.name}"
                counts[base] = counts.get(base, 0) + 1
                path = f"{base}[{counts[base]}]"
                paths[span.id] = path
                result[path] = span
            return result

        a_spans, b_spans = keyed(a), keyed(b)
        for key in dict.fromkeys([*a_spans, *b_spans]):
            x, y = a_spans.get(key), b_spans.get(key)
            fields = [
                field
                for field in ("input", "output", "status", "error", "metadata")
                if x is None or y is None or getattr(x, field) != getattr(y, field)
            ]
            changes.append(
                {
                    "path": key,
                    "change": "added"
                    if x is None
                    else "removed"
                    if y is None
                    else "modified"
                    if fields
                    else "unchanged",
                    "fields": fields,
                    "left": x.model_dump(mode="json") if x else None,
                    "right": y.model_dump(mode="json") if y else None,
                    "duration_delta_ms": (y.duration_ms if y else 0) - (x.duration_ms if x else 0),
                }
            )
        return {
            "left": a.model_dump(mode="json"),
            "right": b.model_dump(mode="json"),
            "duration_delta_ms": b.duration_ms - a.duration_ms,
            "changes": changes,
        }

    return app


app = create_app()
