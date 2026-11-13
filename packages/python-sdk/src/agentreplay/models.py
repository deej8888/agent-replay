from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

Status = Literal["success", "error"]
Kind = Literal["agent", "tool", "llm", "span"]


class ErrorInfo(BaseModel):
    type: str = Field(max_length=200)
    message: str = Field(max_length=4096)


class Span(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID = Field(default_factory=uuid4)
    parent_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    kind: Kind
    sequence: int = Field(ge=0)
    started_at: datetime
    ended_at: datetime
    duration_ms: float = Field(ge=0, allow_inf_nan=False)
    status: Status
    input: JsonValue = None
    output: JsonValue = None
    error: ErrorInfo | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    replayable: bool = True

    @model_validator(mode="after")
    def validate_span(self) -> "Span":
        if self.started_at.tzinfo is None or self.ended_at.tzinfo is None:
            raise ValueError("timestamps must include a timezone")
        if self.ended_at < self.started_at:
            raise ValueError("ended_at must follow started_at")
        if (self.status == "error") != (self.error is not None):
            raise ValueError("error status and error details must agree")
        return self


class Run(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=200)
    started_at: datetime
    ended_at: datetime
    duration_ms: float = Field(ge=0, allow_inf_nan=False)
    status: Status
    input: JsonValue = None
    output: JsonValue = None
    error: ErrorInfo | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    spans: list[Span] = Field(min_length=1, max_length=2000)
    mode: Literal["record", "playback", "reexecution"] = "record"
    source_run_id: UUID | None = None
    replay_report: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def validate_tree(self) -> "Run":
        if self.started_at.tzinfo is None or self.ended_at.tzinfo is None:
            raise ValueError("timestamps must include a timezone")
        if self.ended_at < self.started_at:
            raise ValueError("invalid run timestamps")
        if (self.status == "error") != (self.error is not None):
            raise ValueError("error status and details must agree")
        by_id = {s.id: s for s in self.spans}
        if len(by_id) != len(self.spans):
            raise ValueError("duplicate span IDs")
        roots = [s for s in self.spans if s.parent_id is None]
        if len(roots) != 1 or roots[0].kind != "agent":
            raise ValueError("exactly one root agent span is required")
        if sorted(s.sequence for s in self.spans) != list(range(len(self.spans))):
            raise ValueError("span sequences must be unique and contiguous")
        self.spans.sort(key=lambda s: s.sequence)
        for span in self.spans:
            if span.started_at < self.started_at or span.ended_at > self.ended_at:
                raise ValueError("span timestamps must be within the run")
            if span.parent_id is not None:
                parent = by_id.get(span.parent_id)
                if parent is None or parent.sequence >= span.sequence:
                    raise ValueError("missing parent or cyclic span tree")
                if span.started_at < parent.started_at or span.ended_at > parent.ended_at:
                    raise ValueError("child timestamps must be within parent")
        return self
