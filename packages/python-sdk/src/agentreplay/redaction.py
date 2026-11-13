"""Bounded, conservative JSON capture. Never call an unknown object's repr()."""
import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import JsonValue

SENSITIVE = re.compile(r"password|passwd|secret|token|authorization|api.?key|cookie|credential|ssn|email|phone|address", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
BEARER = re.compile(r"(?i)\b(bearer\s+|sk-)[A-Za-z0-9._-]+")
PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{8,}\d)(?!\w)")


@dataclass
class Redactor:
    sensitive_fields: set[str] = field(default_factory=set)
    max_bytes: int = 16_384
    max_depth: int = 8
    max_items: int = 100

    def text(self, value: str) -> str:
        return PHONE.sub("[REDACTED]", BEARER.sub("[REDACTED]", EMAIL.sub("[REDACTED]", value)))

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
                        str(k)[:200]: "[REDACTED]" if SENSITIVE.search(str(k)) or str(k).lower() in {x.lower() for x in self.sensitive_fields}
                        else visit(v, depth + 1)
                        for k, v in list(item.items())[: self.max_items]
                    }
                else:
                    result = [visit(v, depth + 1) for v in item[: self.max_items]]
                seen.remove(id(item))
                return result
            complete = False
            return f"[UNSUPPORTED:{type(item).__name__}]"

        captured = visit(value)
        encoded = json.dumps(captured, ensure_ascii=True).encode()
        if len(encoded) > self.max_bytes:
            # Hash the sanitized representation, never retain a raw-value fingerprint.
            return {"_truncated": True, "sha256": hashlib.sha256(encoded).hexdigest()}, False
        return captured, complete
