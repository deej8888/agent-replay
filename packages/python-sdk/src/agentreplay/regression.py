"""Export portable pytest fixtures and assert recorded agent behavior offline."""

import asyncio
import inspect
import json
import keyword
from collections.abc import Callable
from copy import deepcopy
from importlib import import_module
from io import BytesIO
from typing import Any, cast
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from .models import Run
from .redaction import Redactor, sanitize_run
from .replay import ReplayDivergence, ReplaySession, same_json
from .tracing import Tracer
from .transport import MemoryTransport

MAX_RECORDING_BYTES = 2_097_152


def _validate_entrypoint(entrypoint: str) -> str:
    if len(entrypoint) > 500 or entrypoint.count(":") != 1:
        raise ValueError("Use a Python entrypoint such as 'my_package.agent:run_agent'")
    module, name = entrypoint.split(":")
    if not all(
        part.isidentifier() and not keyword.iskeyword(part)
        for part in [*module.split("."), *name.split(".")]
    ):
        raise ValueError("The entrypoint must contain importable Python module and callable names")
    if module == "__main__":
        raise ValueError(
            "Move the agent into an importable module or provide an adapter entrypoint"
        )
    return entrypoint


def _resolve_agent(agent: Callable[..., Any] | str) -> Callable[..., Any]:
    if isinstance(agent, str):
        module, name = _validate_entrypoint(agent).split(":")
        target: Any = import_module(module)
        for part in name.split("."):
            target = getattr(target, part)
        if not callable(target):
            raise ValueError("The Python entrypoint must resolve to a callable agent")
        return cast(Callable[..., Any], target)
    return agent


def _recorded_arguments(agent: Callable[..., Any], source: Run) -> inspect.BoundArguments:
    if not isinstance(source.input, dict):
        raise ValueError("Regression tests require named agent inputs captured by @trace_agent")
    signature = inspect.signature(agent)
    if source.input.keys() - signature.parameters.keys():
        raise ValueError("Recorded agent arguments do not match the current Python signature")
    arguments = deepcopy(source.input)
    for name, parameter in signature.parameters.items():
        if parameter.kind == inspect.Parameter.VAR_POSITIONAL and not isinstance(
            arguments.get(name, []), list
        ):
            raise ValueError("Recorded positional varargs must be a JSON array")
        if parameter.kind == inspect.Parameter.VAR_KEYWORD and not isinstance(
            arguments.get(name, {}), dict
        ):
            raise ValueError("Recorded keyword varargs must be a JSON object")
    bound = signature.bind_partial()
    bound.arguments.update(arguments)
    bound.apply_defaults()
    signature.bind(*bound.args, **bound.kwargs)
    return bound


async def assert_replay_async(
    source: Run,
    agent: Callable[..., Any] | str,
    *,
    redactor: Redactor | None = None,
) -> Run:
    """Assert call matching, input, name, output, status, and recorded exceptions.

    A faithfully reproduced recorded failure passes. Signature changes, missing
    captures and replay divergence fail. String entrypoints are imported inside
    the offline context. Only trusted application code should be executed.
    """
    replay = ReplaySession(source)
    capture = MemoryTransport()
    failure: Exception | None = None
    try:
        with Tracer(capture, redactor).use(), replay:
            target = _resolve_agent(agent)
            arguments = _recorded_arguments(target, source)
            result = target(*arguments.args, **arguments.kwargs)
            if inspect.isawaitable(result):
                await result
    except Exception as exc:
        failure = exc

    if isinstance(failure, ReplayDivergence):
        raise AssertionError(f"Offline replay diverged: {failure}") from failure
    if len(capture.runs) != 1:
        raise AssertionError(
            "Expected exactly one completed agent trace during the regression test"
        ) from failure
    actual = capture.runs[0]
    if actual.name != source.name or not same_json(actual.input, source.input):
        raise AssertionError("The agent name or sanitized input differs from the recording")
    if not replay.report["faithful"]:
        raise AssertionError(
            f"Recorded behavior changed: {json.dumps(replay.report, ensure_ascii=True)}"
        ) from failure
    return actual


def assert_replay(
    source: Run,
    agent: Callable[..., Any] | str,
    *,
    redactor: Redactor | None = None,
) -> Run:
    """Run an offline regression assertion for a synchronous or async agent.

    Inside an existing event loop, await assert_replay_async instead.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(assert_replay_async(source, agent, redactor=redactor))
    raise RuntimeError("Use 'await assert_replay_async(...)' inside an active event loop")


def export_regression(
    source: Run, entrypoint: str | None = None, *, redactor: Redactor | None = None
) -> bytes:
    """Build a ZIP with a sanitized recording, pytest test, and instructions.

    Export never imports or executes the provided entrypoint. The same input
    produces the same ZIP bytes, including fixed archive timestamps.
    """
    source = sanitize_run(source, redactor)
    ReplaySession(source)  # Reject incomplete or concurrent recordings before exporting.
    if source.replay_report and source.replay_report.get("faithful") is False:
        raise ValueError("Export the source recording of a diverged replay")
    if not isinstance(source.input, dict):
        raise ValueError("Regression export requires named agent inputs captured by @trace_agent")
    recorded_entrypoint = source.metadata.get("entrypoint")
    entrypoint = entrypoint or (
        recorded_entrypoint if isinstance(recorded_entrypoint, str) else None
    )
    if not entrypoint:
        raise ValueError("Provide the Python entrypoint as 'my_package.agent:run_agent'")
    entrypoint = _validate_entrypoint(entrypoint)
    recording = source.model_dump_json(indent=2) + "\n"
    if len(recording.encode("utf-8")) > MAX_RECORDING_BYTES:
        recording = source.model_dump_json() + "\n"
    if len(recording.encode("utf-8")) > MAX_RECORDING_BYTES:
        raise ValueError("Regression recordings must not exceed 2 MiB")
    suffix = source.id.hex[:12]
    fixture_name = f"recording_{suffix}.json"
    test_name = f"test_agentreplay_{suffix}.py"
    test_source = f'''"""Offline regression for AgentReplay run {source.id}."""
from pathlib import Path

import pytest
from agentreplay import Run, assert_replay

ENTRYPOINT = {entrypoint!r}


@pytest.fixture
def recorded_run() -> Run:
    path = Path(__file__).with_name({fixture_name!r})
    return Run.model_validate_json(path.read_text(encoding="utf-8"))


def test_recorded_agent_behavior(recorded_run: Run) -> None:
    assert_replay(recorded_run, ENTRYPOINT)
'''
    instructions = f"""# AgentReplay regression test

This bundle reproduces run `{source.id}` through offline code re-execution.
The recorded outcome is **{source.status}**. A recorded exception is expected
behavior and passes when reproduced with the same type and sanitized message.

## Run the test

1. Install your agent application and its dependencies in a Python 3.11+ environment.
2. Install the AgentReplay SDK from the checkout that generated this bundle.
   `python -m pip install -e /path/to/agent-replay/packages/python-sdk`
3. Install pytest with `python -m pip install 'pytest>=8.3,<10'`.
4. Keep both generated files together and run `python -m pytest {test_name} -q`.

The test imports the configured entrypoint inside the replay context. Its
module must be available on the Python import path. Keep side effects inside
decorated tool and LLM functions. Review application imports before running
tests from an unfamiliar project. The SDK is intended for trusted Python code.

The assertions check the recorded call sequence, sanitized arguments, agent
name, final output, status, and exception. Extra, changed or missing calls fail
the test. Tool and model implementations are replaced with recorded responses.

The bundle contains sanitized application data. Review it before sharing.
If recording used custom redaction rules, pass the same Redactor configuration
to assert_replay in the generated test. For an instance method, provide an
importable adapter that constructs the instance and accepts the recorded
arguments. Record a new baseline after intentionally changing behavior.

The fixed archive timestamp makes repeated exports reproducible. Original
execution timestamps remain in the recording JSON.
"""
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in {
            fixture_name: recording,
            test_name: test_source,
            "README.md": instructions,
        }.items():
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content.encode("utf-8"))
    return output.getvalue()
