"""Bounded, conservative JSON capture. Never call an unknown object's repr()."""

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from itertools import islice
from typing import Any

from pydantic import JsonValue

from .models import Run

SENSITIVE = re.compile(
    r"password|passwd|secret|token|authorization|api.?key|cookie|credential|ssn|email|phone|address",
    re.I,
)
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
BEARER = re.compile(r"(?i)\b(bearer\s+|sk-)[A-Za-z0-9._-]+")
PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{8,}\d)(?!\w)")
ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization)\s*[:=]\s*[^\s,;]+"
)


@dataclass
class Redactor:
    sensitive_fields: set[str] = field(default_factory=set)
    max_bytes: int = 16_384
    max_depth: int = 8
    max_items: int = 100

    def text(self, value: str) -> str:
        return ASSIGNMENT.sub(
            r"\1=[REDACTED]",
            PHONE.sub("[REDACTED]", BEARER.sub("[REDACTED]", EMAIL.sub("[REDACTED]", value))),
        )

    def capture(self, value: Any) -> tuple[JsonValue, bool]:
        complete = True
        seen: set[int] = set()

        def visit(item: Any, depth: int = 0) -> JsonValue:
            nonlocal complete
            if depth > self.max_depth:
                complete = False
                return "[DEPTH LIMIT]"
            if item is None or isinstance(item, (bool, int)):
                return item
            if isinstance(item, float):
                return item if math.isfinite(item) else str(item)
            if isinstance(item, str):
                clean = self.text(item)
                if len(clean) > self.max_bytes:
                    complete = False
                    return clean[: self.max_bytes] + "[TRUNCATED]"
                return clean
            if isinstance(item, (Mapping, list, tuple)):
                if id(item) in seen:
                    complete = False
                    return "[CYCLE]"
                seen.add(id(item))
                if len(item) > self.max_items:
                    complete = False
                if isinstance(item, Mapping):
                    result: JsonValue = {
                        self.text(str(k))[:200]: "[REDACTED]"
                        if SENSITIVE.search(str(k))
                        or str(k).lower() in {x.lower() for x in self.sensitive_fields}
                        else visit(v, depth + 1)
                        for k, v in islice(item.items(), self.max_items)
                    }
                else:
                    result = [visit(v, depth + 1) for v in item[: self.max_items]]
                seen.remove(id(item))
                return result
            complete = False
            return f"[UNSUPPORTED:{type(item).__name__}]"

        try:
            captured = visit(value)
            encoded = json.dumps(captured, ensure_ascii=True).encode()
        except Exception:
            return "[CAPTURE FAILED]", False
        if len(encoded) > self.max_bytes:
            # Hash the sanitized representation, never retain a raw-value fingerprint.
            return {"_truncated": True, "sha256": hashlib.sha256(encoded).hexdigest()}, False
        return captured, complete


def sanitize_run(run: Run, redactor: Redactor | None = None) -> Run:
    """Sanitize a complete trace without mutating the caller's recording."""
    redactor = redactor or Redactor()
    clean = run.model_copy(deep=True)
    clean.name = redactor.text(clean.name)
    clean.input = redactor.capture(clean.input)[0]
    clean.output = redactor.capture(clean.output)[0]
    metadata, _ = redactor.capture(clean.metadata)
    clean.metadata = metadata if isinstance(metadata, dict) else {"detail": metadata}
    if run.metadata.get("concurrent"):
        clean.metadata["concurrent"] = True
    if clean.error:
        clean.error.message = redactor.text(clean.error.message)
    if clean.replay_report:
        report, _ = redactor.capture(clean.replay_report)
        clean.replay_report = report if isinstance(report, dict) else {"detail": report}
    for span in clean.spans:
        span.name = redactor.text(span.name)
        span.input, complete_input = redactor.capture(span.input)
        span.output, complete_output = redactor.capture(span.output)
        span.replayable = span.replayable and complete_input and complete_output
        span_metadata, _ = redactor.capture(span.metadata)
        span.metadata = (
            span_metadata if isinstance(span_metadata, dict) else {"detail": span_metadata}
        )
        if span.error:
            span.error.message = redactor.text(span.error.message)
    return clean
