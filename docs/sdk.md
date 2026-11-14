# SDK integration

Install from this checkout with `pip install -e ./packages/python-sdk`. The package depends only on Pydantic and httpx. The API and example packages are separate.

## Sync and async

Decorate the top-level agent with `@trace_agent`, every tool with `@trace_tool`, and optional model adapters with `@trace_llm(model="model-name")`. Both bare decorators and configured decorators preserve the callable type. `Tracer(exporter).use()` selects an exporter for the current context.

```python
from agentreplay import BufferedHTTPTransport, Redactor, Tracer, trace_agent, trace_tool


@trace_tool(name="fetch-record")
async def fetch_record(record_id: str) -> dict:
    return {"record_id": record_id, "customer_name": "Example Person"}


@trace_agent(metadata={"environment": "development", "version": "my-git-sha"})
async def agent(record_id: str) -> dict:
    return await fetch_record(record_id)


redactor = Redactor(sensitive_fields={"customer_name", "internal_notes"})
with BufferedHTTPTransport() as exporter:
    with Tracer(exporter, redactor).use():
        result = await agent("sample-1")  # inside your async entry point
```

The actual caller still receives the original, unredacted return value. Only the captured copy is sanitized. Exceptions propagate normally. Transport errors are logged without payloads and never replace an agent result.

## Context managers

```python
from agentreplay import MemoryTransport, Tracer

capture = MemoryTransport()
tracer = Tracer(capture)
with tracer.use(), tracer.span("my-agent", kind="agent", inputs={"task": "demo"}) as root:
    with tracer.span("choose-strategy", inputs={"candidates": 2}) as decision:
        decision["output"] = "search-first"
    root["output"] = "done"

run = capture.runs[0]
```

Manually authored tool/LLM contexts record data but cannot safely skip their bodies during replay, so they make the trace non-replayable. Use decorated functions at integration boundaries.

## Sanitization and budgets

Sensitive field-name patterns include passwords, tokens, authorization, API keys, cookies, credentials, SSNs, email, phone and address. String sanitization covers common email/phone, bearer-token, `sk-` credential and credential-assignment patterns. Add application-specific field names with `sensitive_fields`; override the `Redactor.text` method for additional domain-specific patterns.

Defaults: 16,384 bytes per captured value, depth 8, 100 entries per collection, 2,000 spans per run, 2 MiB serialized run. Oversized individual values become a marker plus a hash of their **sanitized** representation. Incomplete values are flagged and cannot be re-executed. An oversized complete run is dropped with a payload-free warning. Unknown objects are not introspected or repr-serialized. Use plain JSON-compatible return values for replay.

Set explicit names for decorated bound methods: receiver instances are excluded from captures. Names and metadata should describe code paths and versions, never contain secrets. Regex redaction is not a substitute for deciding which data should be captured.

## Delivery

`BufferedHTTPTransport(url=..., api_key=..., capacity=128)` submits completed runs from a background thread. A full queue drops new runs. HTTP requests have a three-second timeout and do not inherit proxy settings (`trust_env=False`). There are no retries or disk spool. `failed` counts unsuccessful deliveries; `dropped` counts full-queue/closed-transport drops. Calling `close()` drains queued attempts, so shutdown can take time when the API is unavailable. Process termination without closing may lose buffered traces.

For tests and local files, `MemoryTransport` keeps complete models in `.runs`. Create a fresh instance per test or clear it for long-lived applications. An implicit tracer without an explicit `Tracer.use()` has a null exporter and retains no runs.

## Regression test export

`export_regression(run, entrypoint=None, redactor=None)` returns a ZIP with a pytest test, recording JSON, and instructions. Importable `@trace_agent` functions add an `entrypoint` metadata field automatically. You can supply or override the target when exporting. The exporter generates files without importing the target.

`assert_replay(run, callable_or_entrypoint, redactor=None)` checks the reproduced behavior and returns the actual run. Use `await assert_replay_async(...)` from an active async context. The CLI command `python -m agentreplay export-test recording.json --entrypoint my_app:agent --output regression.zip` provides the same export. See [the regression testing guide](regression-tests.md).
