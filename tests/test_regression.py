import json
import subprocess
import sys
from io import BytesIO
from zipfile import ZipFile

import pytest
from agentreplay import (
    MemoryTransport,
    Redactor,
    ReplayDivergence,
    Tracer,
    assert_replay,
    assert_replay_async,
    export_regression,
    trace_agent,
    trace_tool,
)
from agentreplay.redaction import sanitize_run
from agentreplay_examples.agent import shopping_agent


@pytest.mark.parametrize("fail", [False, True])
def test_exported_test_runs_in_pytest(tmp_path, fail):
    capture = MemoryTransport()
    with Tracer(capture).use():
        try:
            shopping_agent("Find a keyboard", simulate_failure=fail)
        except ValueError:
            pass
    source = capture.runs[0]
    archive = export_regression(source)
    assert export_regression(source) == archive
    with ZipFile(BytesIO(archive)) as bundle:
        assert len(bundle.namelist()) == 3
        assert all("/" not in name and "\\" not in name for name in bundle.namelist())
        bundle.extractall(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(tmp_path), "-q"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


def test_regression_rejects_changed_final_output(recorded):
    @trace_agent(name="shopping-assistant")
    def changed_agent(request, simulate_failure=False):
        shopping_agent(request, simulate_failure)
        return "changed answer"

    with pytest.raises(AssertionError, match="Recorded behavior changed"):
        assert_replay(recorded, changed_agent)


def test_regression_rejects_missing_and_extra_calls(recorded):
    @trace_agent(name="shopping-assistant")
    def missing(request, simulate_failure=False):
        return recorded.output

    with pytest.raises(AssertionError, match="Offline replay diverged"):
        assert_replay(recorded, missing)

    @trace_agent(name="shopping-assistant")
    def extra(request, simulate_failure=False):
        shopping_agent(request, simulate_failure)
        return shopping_agent(request, simulate_failure)

    with pytest.raises(AssertionError, match="exhausted"):
        assert_replay(recorded, extra)


def test_regression_checks_expected_exception_type_and_message():
    capture = MemoryTransport()
    with Tracer(capture).use(), pytest.raises(ValueError):
        shopping_agent("Find a keyboard", True)
    source = capture.runs[0]

    @trace_agent(name="shopping-assistant")
    def changed(request, simulate_failure=False):
        try:
            shopping_agent(request, simulate_failure)
        except ValueError as exc:
            raise RuntimeError("different failure") from exc

    with pytest.raises(AssertionError, match="Recorded behavior changed"):
        assert_replay(source, changed)


async def test_async_regression_and_full_python_signature():
    capture = MemoryTransport()

    @trace_tool
    async def tool(values):
        return sum(values)

    @trace_agent
    async def agent(first, /, *extra, scale=1, **options):
        return await tool([first, *extra, *options.values()]) * scale

    with Tracer(capture).use():
        await agent(1, 2, 3, scale=2, last=4)
    source = capture.runs[0]
    assert (await assert_replay_async(source, agent)).output == 20
    with pytest.raises(RuntimeError, match="await assert_replay_async"):
        assert_replay(source, agent)


def test_sync_assertion_accepts_async_agent():
    capture = MemoryTransport()
    import asyncio

    @trace_agent
    async def agent(value):
        return value

    with Tracer(capture).use():
        asyncio.run(agent(7))
    assert assert_replay(capture.runs[0], agent).output == 7


def test_changed_signature_and_missing_instrumentation_cannot_pass(recorded):
    def renamed_argument(other):
        pytest.fail("Signature mismatch must be detected before calling application code")

    with pytest.raises(AssertionError, match="exactly one completed agent trace"):
        assert_replay(recorded, renamed_argument)

    def raw_agent(request, simulate_failure=False):
        return recorded.output

    with pytest.raises(AssertionError, match="Missing 3 recorded call"):
        assert_replay(recorded, raw_agent)


def test_entrypoint_import_happens_in_offline_context(tmp_path, monkeypatch, recorded):
    (tmp_path / "network_import_trap.py").write_text(
        "import socket\nsocket.getaddrinfo('example.com', 443)\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(AssertionError, match="Network access is forbidden"):
        assert_replay(recorded, "network_import_trap:agent")


def test_export_never_imports_entrypoint_or_embeds_its_text_as_code(recorded, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Export must not import application code")

    monkeypatch.setattr("agentreplay.regression.import_module", forbidden)
    archive = export_regression(recorded, "not_installed.agent:Agent.run")
    with ZipFile(BytesIO(archive)) as bundle:
        code = bundle.read(next(n for n in bundle.namelist() if n.endswith(".py"))).decode()
        assert "ENTRYPOINT = 'not_installed.agent:Agent.run'" in code
        compile(code, "exported_test.py", "exec")
    with pytest.raises(ValueError, match="entrypoint"):
        export_regression(recorded, "bad:agent\n__import__('os').system('something')")


def test_export_redacts_copies_and_preserves_concurrency_signal(recorded):
    recorded.metadata["api_key"] = "do-not-share-this"
    recorded.spans[1].metadata["contact"] = "person@example.com"
    archive = export_regression(recorded)
    with ZipFile(BytesIO(archive)) as bundle:
        recording = bundle.read(next(n for n in bundle.namelist() if n.endswith(".json")))
        assert b"do-not-share-this" not in recording
        assert b"person@example.com" not in recording
    assert recorded.metadata["api_key"] == "do-not-share-this"
    recorded.metadata = {**{f"label_{i}": i for i in range(100)}, "concurrent": True}
    assert sanitize_run(recorded).metadata["concurrent"] is True
    with pytest.raises(ReplayDivergence, match="Concurrent"):
        export_regression(recorded, "my_app:agent")


def test_custom_redaction_is_supported_in_regression():
    capture = MemoryTransport()
    redactor = Redactor(sensitive_fields={"customer_name"})

    @trace_agent
    def agent(customer_name):
        return {"customer_name": customer_name}

    with Tracer(capture, redactor).use():
        agent("Private Person")
    assert assert_replay(capture.runs[0], agent, redactor=redactor).status == "success"


def test_cli_exports_and_generated_test_fails_after_baseline_changes(tmp_path, recorded):
    source_path = tmp_path / "source.json"
    source_path.write_text(recorded.model_dump_json(), encoding="utf-8")
    archive_path = tmp_path / "regression.zip"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agentreplay",
            "export-test",
            str(source_path),
            "--output",
            str(archive_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    with ZipFile(archive_path) as bundle:
        bundle.extractall(tmp_path)
    fixture = next(tmp_path.glob("recording_*.json"))
    baseline = json.loads(fixture.read_text(encoding="utf-8"))
    baseline["output"] = "outdated answer"
    fixture.write_text(json.dumps(baseline), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(next(tmp_path.glob("test_*.py"))), "-q"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=tmp_path,
    )
    assert result.returncode == 1
    assert "Recorded behavior changed" in result.stdout


def test_incomplete_and_diverged_runs_cannot_be_exported(recorded):
    recorded.spans[1].replayable = False
    with pytest.raises(ReplayDivergence, match="unsupported"):
        export_regression(recorded)
    recorded.spans[1].replayable = True
    recorded.replay_report = {"faithful": False, "divergences": ["changed input"]}
    with pytest.raises(ValueError, match="source recording"):
        export_regression(recorded)
