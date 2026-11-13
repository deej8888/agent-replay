import functools
import inspect
import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ParamSpec, TypeVar, cast
from uuid import UUID, uuid4

from pydantic import JsonValue

from .models import ErrorInfo, Kind, Run, Span
from .redaction import Redactor
from .replay import active_replay
from .transport import MemoryTransport, Transport

P = ParamSpec("P")
R = TypeVar("R")
log = logging.getLogger("agentreplay")


@dataclass
class Recorder:
    id: UUID = field(default_factory=uuid4)
    spans: list[Span] = field(default_factory=list)
    sequence: int = 0
    active_boundaries: int = 0
    concurrent: bool = False
    overflow: bool = False


recorder_context: ContextVar[Recorder | None] = ContextVar("agentreplay_recorder", default=None)
parent_context: ContextVar[UUID | None] = ContextVar("agentreplay_parent", default=None)
tracer_context: ContextVar["Tracer | None"] = ContextVar("agentreplay_tracer", default=None)


class Tracer:
    def __init__(self, transport: Transport | None = None, redactor: Redactor | None = None) -> None:
        self.transport = transport if transport is not None else MemoryTransport()
        self.redactor = redactor or Redactor()

    @contextmanager
    def use(self) -> Iterator["Tracer"]:
        token = tracer_context.set(self)
        try:
            yield self
        finally:
            tracer_context.reset(token)

    @contextmanager
    def span(self, name: str, *, kind: Kind = "span", inputs: Any = None, metadata: dict[str, JsonValue] | None = None) -> Iterator[dict[str, Any]]:
        recorder = recorder_context.get()
        is_root = recorder is None
        recorder_token = None
        if recorder is None:
            if kind != "agent":
                raise ValueError("Start an agent span before child spans")
            recorder = Recorder()
            recorder_token = recorder_context.set(recorder)
        sequence = recorder.sequence
        recorder.sequence += 1
        if sequence >= 2000:
            recorder.overflow = True
        span_id = uuid4()
        parent_id = parent_context.get()
        parent_token = parent_context.set(span_id)
        started = datetime.now(UTC)
        clock = time.perf_counter()
        captured_input, input_complete = self.redactor.capture(inputs)
        captured_metadata, _ = self.redactor.capture(metadata or {})
        state: dict[str, Any] = {"output": None, "input": captured_input}
        error: ErrorInfo | None = None
        try:
            yield state
        except BaseException as exc:
            error = ErrorInfo(type=type(exc).__name__, message=self.redactor.text(str(exc))[:4096])
            raise
        finally:
            ended = datetime.now(UTC)
            output, output_complete = self.redactor.capture(state["output"])
            span = Span(id=span_id, parent_id=parent_id, name=name[:200], kind=kind, sequence=sequence, started_at=started, ended_at=ended, duration_ms=(time.perf_counter() - clock) * 1000, status="error" if error else "success", input=captured_input, output=output, error=error, metadata=cast(dict[str, JsonValue], captured_metadata) if isinstance(captured_metadata, dict) else {}, replayable=input_complete and output_complete)
            if sequence < 2000:
                recorder.spans.append(span)
            parent_context.reset(parent_token)
            if is_root:
                assert recorder_token is not None
                recorder_context.reset(recorder_token)
                # Overlong/detached executions cannot produce a valid complete tree.
                if not recorder.overflow:
                    try:
                        run = Run(id=recorder.id, name=name[:200], started_at=started, ended_at=ended, duration_ms=span.duration_ms, status=span.status, input=span.input, output=output, error=error, metadata={**span.metadata, "concurrent": recorder.concurrent}, spans=sorted(recorder.spans, key=lambda s: s.sequence))
                        self.transport.submit(run)
                    except Exception:
                        log.warning("AgentReplay capture/export failed (no payload logged)")
                else:
                    log.warning("AgentReplay span limit exceeded; trace dropped")


default_tracer = Tracer()


def _decorate(kind: Kind, name: str | None, metadata: dict[str, JsonValue] | None) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorate(fn: Callable[P, R]) -> Callable[P, R]:
        signature = inspect.signature(fn)
        span_name = name or fn.__name__

        def prepare(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            return {k: v for k, v in bound.arguments.items() if k not in ("self", "cls")}

        @contextmanager
        def invocation(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Iterator[tuple[dict[str, Any], bool]]:
            tracer = tracer_context.get() or default_tracer
            if recorder_context.get() is None and kind != "agent" and active_replay.get() is None:
                yield {}, False
                return
            inputs = prepare(args, kwargs)
            recorder = recorder_context.get()
            boundary = kind in ("tool", "llm")
            # Overlapping sibling boundaries are ambiguous; nested boundaries are safe.
            if recorder and boundary:
                active_parent = parent_context.get()
                if recorder.active_boundaries and not any(s.id == active_parent and s.kind in ("tool", "llm") for s in recorder.spans):
                    recorder.concurrent = True
                recorder.active_boundaries += 1
            try:
                with tracer.span(span_name, kind=kind, inputs=inputs, metadata=metadata) as state:
                    yield state, True
            finally:
                if recorder and boundary:
                    recorder.active_boundaries -= 1

        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                with invocation(args, kwargs) as (state, recording):
                    replay = active_replay.get()
                    if replay and kind in ("tool", "llm"):
                        result = replay.resolve(span_name, kind, state["input"])
                    else:
                        result = await fn(*args, **kwargs)
                    if recording:
                        state["output"] = result
                    return result
            return cast(Callable[P, R], async_wrapper)

        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with invocation(args, kwargs) as (state, recording):
                replay = active_replay.get()
                result = replay.resolve(span_name, kind, state["input"]) if replay and kind in ("tool", "llm") else fn(*args, **kwargs)
                if recording:
                    state["output"] = result
                return cast(R, result)
        return wrapper
    return decorate


def trace_agent(fn: Callable[P, R] | None = None, *, name: str | None = None, metadata: dict[str, JsonValue] | None = None) -> Any:
    decorator = _decorate("agent", name, metadata)
    return decorator(fn) if fn else decorator


def trace_tool(fn: Callable[P, R] | None = None, *, name: str | None = None) -> Any:
    decorator = _decorate("tool", name, None)
    return decorator(fn) if fn else decorator


def trace_llm(fn: Callable[P, R] | None = None, *, name: str | None = None, model: str | None = None) -> Any:
    decorator = _decorate("llm", name, {"model": model} if model else None)
    return decorator(fn) if fn else decorator
