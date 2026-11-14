# API reference

Base URL: `http://127.0.0.1:8000`. OpenAPI UI: `/docs`. Interactive docs and all `/v1` routes require `X-API-Key` when `AGENTREPLAY_API_KEY` is configured; `/health` remains public. The Next.js server proxy supplies the configured key.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/health` | Process liveness |
| POST | `/v1/runs` | Validate, sanitize, and atomically ingest one complete run and its spans (201) |
| GET | `/v1/runs` | Paginated summaries, newest original start time first |
| GET | `/v1/runs/{run_id}` | Full run with flat parent-linked spans in start order |
| GET | `/v1/runs/{run_id}/regression?entrypoint=my_app.agent:run_agent` | Download a ZIP containing a sanitized fixture and runnable pytest test |
| GET | `/v1/runs/{run_id}/spans/{span_id}` | Span input, output, error and metadata |
| POST | `/v1/demo` | Record a no-key demo; body `{ "request": "Find a keyboard", "fail": false }` |
| POST | `/v1/runs/{run_id}/replays` | Create playback or demo re-execution |
| GET | `/v1/compare?left={id}&right={id}` | Both complete runs plus aligned span differences |

Listing accepts `q` (agent name or run ID), `status=success|error`, `model`, `mode=record|playback|reexecution`, `limit` (1–100, default 50), and `offset`. The response contains `items`, `total`, `limit`, and `offset`. Summaries intentionally omit spans. Playback preserves the source start time, so it appears beside its source rather than at creation time.

Replay requires a `mode`:

```json
{"mode": "reexecution", "simulate_divergence": false}
```

`simulate_divergence` changes the bundled demo request to demonstrate strict input matching. It has no effect in playback mode. Server re-execution only accepts the bundled `shopping-demo` target and validates its agent input. Other agents use the Python SDK in their own application environment. Responses are stored derived runs with `source_run_id`, `mode`, and `replay_report`.

Run/span schemas are defined in `packages/python-sdk/src/agentreplay/models.py`. Input/output values are JSON. Error details contain a type and sanitized message. Root agents have no parent; all other spans must reference an earlier sequence in the same run. Timestamps require explicit timezones and must be contained within their parents/run. The server sorts valid spans by sequence.

Errors use standard HTTP status codes: 401 for an invalid/missing configured key; 404 for missing records; 409 for duplicate run/span IDs; 413 for bodies over 2 MiB; 422 for validation and non-replayable sources. An executed demo divergence is a valid newly stored failed run (201), with its mismatch in the replay report. Validation responses omit raw input payloads.

Regression export returns `application/zip` with a download filename in `Content-Disposition`. It does not import the requested entrypoint. The optional `entrypoint` query parameter defaults to captured metadata or the legacy shopping-demo target. Invalid entrypoints, incomplete/concurrent sources, diverged replay results and unsupported agent inputs return 422. The Next.js proxy preserves binary responses and download headers.
