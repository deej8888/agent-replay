# AgentReplay

[![CI](https://github.com/deej8888/agent-replay/actions/workflows/ci.yaml/badge.svg)](https://github.com/deej8888/agent-replay/actions/workflows/ci.yaml)

**Understand every step your agent took. Reproduce the one that went wrong.**

AgentReplay is a local-first debugger for Python agents. Record prompts, model responses, tool calls, and failures; inspect the execution tree; then re-run instrumented code using recorded responses, without calling real integrations.

MIT licensed. Python 3.11+. No API key needed for the demo.

![AgentReplay execution dashboard](docs/screenshots/dashboard.png)
![A recorded failure and its nested execution timeline](docs/screenshots/execution.png)

## Quick start

Requires Python 3.11+ and Node.js 22.12+ (Node 24 recommended). From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]' -e ./packages/python-sdk -e ./examples -e ./apps/api
python -m uvicorn agentreplay_api.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd apps/web
npm ci
npm run dev
```

Open **http://127.0.0.1:3000**. Click **Run demo agent** or **Record a failure**. Select a timeline step to inspect its input, output, error, and metadata. From a demo run, **Re-execute offline** reproduces the recorded behavior. **Simulate divergence** changes the request and demonstrates strict matching. Select any two executions in the table to compare them.

SQLite is created automatically in the directory where you start the API. Alembic applies versioned migrations on startup. API documentation: **http://127.0.0.1:8000/docs**.

## Record and reproduce a failure from the terminal

Activate the virtual environment, then:

```bash
agentreplay-demo --submit --output success.json
agentreplay-demo --fail --submit --output failure.json
agentreplay-demo --replay failure.json
```

The last command re-executes the shopping agent, substitutes the two recorded tool results, and raises the same inventory validation failure. Its report shows `offline: true`, `matched_calls: 2`, and `faithful: true`. It works with the API stopped. Recording files contain sanitized trace data; review them before sharing.

## Instrument your agent

```python
from agentreplay import BufferedHTTPTransport, Tracer, trace_agent, trace_tool, trace_llm


@trace_tool
def search(query: str) -> list[str]:
    return ["A useful result"]


@trace_llm(model="my-model")
def generate(prompt: str) -> str:
    return "Your model adapter goes here"


@trace_agent
def my_agent(request: str) -> str:
    return generate(f"{request}: {search(request)}")


with BufferedHTTPTransport() as exporter:
    with Tracer(exporter).use():
        answer = my_agent("Find something useful")
```

Decorators preserve sync/async signatures and propagate context across awaited calls. An agent can also contain nested agents and custom spans. `Tracer.use()` scopes the exporter without changing decorated functions. Exports use a bounded background queue; transport errors do not replace application results. `close()` (or the transport context manager) drains queued traces. Check `failed` and `dropped` for delivery loss. There is no automatic network submission until you configure a transport.

For custom decision spans and configurable redaction, see [the SDK guide](docs/sdk.md).

## Two different kinds of replay

| Action | Application code runs? | What you learn |
| --- | --- | --- |
| **View playback** | No | Inspect an exact copy of the saved trace with original timings. |
| **Re-execute offline** | Yes, the bundled demo | Test application logic with recorded tool/model responses, strict call ordering, and divergence reports. |
| SDK `ReplaySession(run)` | Yes, your instrumented code | Reproduce your own agent locally with recorded boundary responses. |

Replay matches the boundary kind, name, sequence, and normalized sanitized arguments, including JSON primitive types. It bypasses the implementation of every `@trace_tool` and `@trace_llm` call. Extra, changed, and missing calls are reported. There is no fallback to a real integration. A Python audit guard rejects socket operations in the active replay context.

**The SDK is not a sandbox for arbitrary Python code.** Keep all side effects inside decorated boundaries. Filesystem writes, subprocesses, C extensions, and newly spawned threads are not sandboxed. The server only re-executes the allowlisted, side-effect-free demo; it never imports uploaded code. Concurrent boundary recordings, incomplete captures, and manual tool/LLM context-manager spans are rejected for re-execution. See [replay semantics and limitations](docs/replay.md).

## Docker

```bash
docker compose up --build
```

Open http://127.0.0.1:3000. Traces persist in the `traces` volume. Both published ports bind to loopback. The containers run as non-root users.

For PostgreSQL, set a URL-safe `POSTGRES_PASSWORD` in your environment and run:

```bash
docker compose -f compose.yaml -f compose.postgres.yaml up --build
```

You can also point the API at an existing database with `AGENTREPLAY_DATABASE_URL=postgresql+psycopg://user:password@localhost/agentreplay`. Use URL encoding for special characters in connection strings. Keep one API worker while automatic migrations run; larger deployments should apply migrations before starting workers.

## Configuration and security

See [.env.example](.env.example) for settings. The API supports `--env-file .env`; Next.js reads `apps/web/.env.local`. Export environment variables explicitly for the CLI. Docker Compose reads root `.env` values for substitution. Never commit either file.

The optional `AGENTREPLAY_API_KEY` protects direct backend requests with `X-API-Key`. Give the same key to the SDK and Next.js server. The Next.js proxy keeps it off the browser. The web UI is a local, single-user application: that shared key is **not web-user authentication**. Put an authenticated reverse proxy in front of both services if hosting them beyond loopback.

Captured credentials and common email/phone patterns are redacted. Values are bounded to 16 KiB, 100 collection items, and 8 nesting levels by default; runs are capped at 2,000 spans and 2 MiB. Payloads are sanitized again at ingestion. Unknown Python objects are described by type without calling `repr`. Captures that lose information cannot be re-executed. Redaction is best effort; add domain-specific sensitive fields and inspect traces before sharing. Database files are unencrypted and contain application data. See [SECURITY.md](SECURITY.md).

## Test and contribute

```bash
ruff check .
ruff format --check .
mypy
pytest -q
cd apps/web
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Browser tests start an isolated API, temporary SQLite database, and production Next.js server on ports 8011 and 3011. On Windows they use the root `.venv`; override `AGENTREPLAY_TEST_PYTHON` to select another interpreter. Optional PostgreSQL integration tests run when `AGENTREPLAY_TEST_POSTGRES` is set. CI runs Python 3.11/3.13 checks, browser tests, PostgreSQL integration, and a Docker smoke test.

Start with [CONTRIBUTING.md](CONTRIBUTING.md), [architecture](docs/architecture.md), and [the API guide](docs/api.md).

## MVP scope and next steps

The working MVP includes the SDK, buffered capture, SQLite/PostgreSQL storage, migrations, dashboard, filtering and pagination, nested timeline, JSON inspector, behavioral comparison, trace playback, strict offline re-execution, failure reproduction, and a separate optional provider adapter.

Deferred: multi-user authentication and tenancy, streaming live spans, durable export queues/retries, distributed tracing, framework-specific auto-instrumentation, token/cost analytics, parallel-call replay, time/randomness virtualization, arbitrary server-side agent execution, and application sandboxing. These require separate designs; the UI does not present them as available.

The optional [real provider adapter](examples/agentreplay_examples/provider.py) requires `OPENAI_API_KEY` and an explicit `OPENAI_MODEL`. It uses the [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create) with storage disabled. The demo and tests use the fake adapter; no live paid-provider call is made during setup or verification.

## License

[MIT](LICENSE).
