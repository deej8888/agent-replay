"""Strict ordered mocks for instrumented boundaries; this is not a Python sandbox."""

import builtins
from contextvars import ContextVar, Token
from typing import Any

from pydantic import JsonValue

from .models import Run, Span


class ReplayDivergence(RuntimeError):
    pass


class RecordedCallError(RuntimeError):
    pass


active_replay: ContextVar["ReplaySession | None"] = ContextVar("agentreplay_replay", default=None)


class ReplaySession:
    def __init__(self, source: Run) -> None:
        if any(not s.replayable for s in source.spans):
            raise ReplayDivergence(
                "Trace contains truncated or unsupported values and cannot be replayed"
            )
        if source.metadata.get("concurrent"):
            raise ReplayDivergence("Concurrent boundary calls cannot be replayed deterministically")
        self.source = source
        by_id = {s.id: s for s in source.spans}

        def inside_boundary(span: Span) -> bool:
            parent = by_id.get(span.parent_id) if span.parent_id else None
            while parent:
                if parent.kind in ("tool", "llm"):
                    return True
                parent = by_id.get(parent.parent_id) if parent.parent_id else None
            return False

        self.calls = [
            s
            for s in sorted(source.spans, key=lambda s: s.sequence)
            if s.kind in ("tool", "llm") and not inside_boundary(s)
        ]
        self.cursor = 0
        self.divergences: list[JsonValue] = []
        self.token: Token[ReplaySession | None] | None = None

    def fail(self, message: str) -> None:
        self.divergences.append({"position": self.cursor, "message": message})
        raise ReplayDivergence(message)

    def resolve(self, name: str, kind: str, inputs: JsonValue) -> Any:
        if self.cursor >= len(self.calls):
            self.fail(f"Unexpected {kind} call: {name}; recording exhausted")
        expected = self.calls[self.cursor]
        if expected.name != name or expected.kind != kind or expected.input != inputs:
            self.fail(
                f"Call {self.cursor}: expected {expected.kind} {expected.name} with matching sanitized input; received {kind} {name}"
            )
        self.cursor += 1
        if expected.error:
            safe_errors = {
                "ValueError",
                "RuntimeError",
                "KeyError",
                "TypeError",
                "LookupError",
                "TimeoutError",
            }
            if expected.error.type in safe_errors:
                error_type = getattr(builtins, expected.error.type)
                raise error_type(expected.error.message)
            raise RecordedCallError(f"{expected.error.type}: {expected.error.message}")
        return expected.model_copy(deep=True).output

    @property
    def report(self) -> dict[str, JsonValue]:
        return {
            "offline": True,
            "matched_calls": self.cursor,
            "total_calls": len(self.calls),
            "missing_calls": [s.name for s in self.calls[self.cursor :]],
            "divergences": self.divergences,
            "faithful": not self.divergences and self.cursor == len(self.calls),
        }

    def observe_result(self, run: Run) -> None:
        if (
            run.output != self.source.output
            or run.status != self.source.status
            or run.error != self.source.error
        ):
            self.divergences.append(
                {"message": "Final output, status, or exception differs from the recording"}
            )

    def __enter__(self) -> "ReplaySession":
        if active_replay.get() is not None:
            raise ReplayDivergence("Replay sessions cannot be nested")
        self.token = active_replay.set(self)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        assert self.token is not None
        active_replay.reset(self.token)
        if self.cursor != len(self.calls):
            message = f"Missing {len(self.calls) - self.cursor} recorded call(s)"
            self.divergences.append({"position": self.cursor, "message": message})
            if exc is None:
                raise ReplayDivergence(message)
