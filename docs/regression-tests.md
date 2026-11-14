# Regression tests from recordings

AgentReplay exports a pytest test and a recording fixture from an execution. The test imports your Python agent, invokes it with the captured arguments, and supplies recorded responses at tool and model boundaries. Run it locally or add both generated files to your application's test suite.

## Export through the debugger

Open a run, expand **Regression test** with **Export pytest**, and confirm the **Python entrypoint**. Use a module and callable separated by a colon, such as `my_app.agent:run_agent`. **Download test bundle** saves a ZIP containing the test, JSON fixture, and README with environment setup instructions.

New importable agents automatically record their module and qualified name. A class method that needs an instance should use an importable adapter with the same named arguments and recorded agent name. Decorate all integrations used by that adapter. Older shopping-demo recordings resolve to the bundled demo entrypoint automatically.

Export validates and sanitizes data and generates files. The entrypoint is imported when pytest runs the generated test. Imports happen inside the offline replay context, where common socket operations are blocked. Use trusted application code and keep side effects inside decorated integration functions. Replay's existing isolation limits still apply.

## Export from Python or the CLI

```python
from pathlib import Path
from agentreplay import Run, export_regression

source = Run.model_validate_json(Path("recording.json").read_text(encoding="utf-8"))
bundle = export_regression(source, "my_app.agent:run_agent")
Path("regression.zip").write_bytes(bundle)
```

```bash
python -m agentreplay export-test recording.json --entrypoint my_app.agent:run_agent --output regression.zip
python -m zipfile -e regression.zip tests/recorded-agent
python -m pytest tests/recorded-agent -q
```

The installed `agentreplay export-test` console command supports the same arguments. `--entrypoint` is optional when it was captured in run metadata. Install your application, the SDK version from this checkout, and pytest in the test environment.

## Assertion behavior

`assert_replay(recording, callable_or_entrypoint)` returns the newly captured `Run` after checking strict boundary matching and the root agent name, sanitized input, output, status, and exception. A changed signature, missing root instrumentation, extra or missing boundary call, mismatched input, changed final output, or changed exception fails the test. JSON primitive types are compared strictly.

Recorded errors are expected outcomes. A test exported from a failed run passes when the same failure is reproduced. This preserves a reproduction of the failure. After fixing application behavior, update the fixture with a new recording that represents the intended outcome. Existing replay limitations on exception reconstruction can cause a recorded error to diverge, which the test reports.

The synchronous helper supports both sync and async agents using its own event loop. It handles positional-only, keyword-only, default, variadic positional, and variadic keyword parameters from captured named arguments. Inside an existing event loop, use the asynchronous helper.

```python
from agentreplay import Redactor, assert_replay, assert_replay_async

actual = assert_replay(source, "my_app.agent:run_agent")
assert actual.status == "success"

# Inside your asynchronous test or application:
actual = await assert_replay_async(source, "my_app.agent:run_agent")

# Use the same custom configuration as recording:
actual = assert_replay(
    source,
    "my_app.agent:run_agent",
    redactor=Redactor(sensitive_fields={"customer_name"}),
)
```

## Sharing and reproducibility

Export uses the ingestion sanitizer and copies the source before processing it. Credentials and common PII patterns are redacted again. A complete recording must fit within 2 MiB. Incomplete captures, concurrent boundary recordings, and already diverged replays are rejected. For a diverged replay, export the original source run.

Each ZIP has relative filenames, fixed archive timestamps and stable serialization. Repeated exports of the same recording and entrypoint produce the same bytes. The original execution timestamps remain in the JSON fixture. The bundle contains application data, so review it before sharing.
