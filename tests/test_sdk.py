import asyncio

import pytest
from agentreplay import MemoryTransport, Redactor, Tracer, trace_agent, trace_llm, trace_tool


def test_nested_capture_and_defaults():
    transport = MemoryTransport()

    @trace_tool
    def tool(value: int = 2):
        return value * 2

    @trace_llm(model="fake")
    def llm(value: int):
        return str(value)

    @trace_agent
    def agent():
        return llm(tool())

    with Tracer(transport).use():
        assert agent() == "4"
    run = transport.runs[0]
    assert [s.kind for s in run.spans] == ["agent", "tool", "llm"]
    assert run.spans[1].input == {"value": 2}
    assert all(s.parent_id == run.spans[0].id for s in run.spans[1:])
    assert run.status == "success" and run.duration_ms >= 0


async def test_async_propagation_and_run_isolation():
    transport = MemoryTransport()

    @trace_tool
    async def tool(value: int):
        await asyncio.sleep(0)
        return value

    @trace_agent
    async def agent(value: int):
        return await tool(value)

    with Tracer(transport).use():
        assert await asyncio.gather(agent(1), agent(2)) == [1, 2]
    assert len(transport.runs) == 2
    assert len({r.id for r in transport.runs}) == 2
    assert all(len(r.spans) == 2 for r in transport.runs)
    assert all(r.spans[1].parent_id == r.spans[0].id for r in transport.runs)


def test_failure_preserves_application_exception():
    transport = MemoryTransport()

    @trace_tool
    def fail():
        raise ValueError("token=super-secret failed for person@example.com")

    @trace_agent
    def agent():
        return fail()

    with Tracer(transport).use(), pytest.raises(ValueError, match="super-secret"):
        agent()
    serialized = transport.runs[0].model_dump_json()
    assert "super-secret" not in serialized
    assert "person@example.com" not in serialized
    assert all(s.status == "error" for s in transport.runs[0].spans)


def test_redaction_and_payload_bounds():
    redactor = Redactor(sensitive_fields={"customer_name"}, max_bytes=200)
    captured, complete = redactor.capture({"API_KEY": "private", "nested": {"customer_name": "Private Person"}, "note": "person@example.com"})
    assert "private" not in str(captured).lower()
    assert "Private Person" not in str(captured)
    assert complete
    captured, complete = redactor.capture("x" * 5000)
    assert not complete and len(str(captured)) < 200
    cycle = []
    cycle.append(cycle)
    assert not redactor.capture(cycle)[1]


def test_unknown_objects_do_not_invoke_repr():
    class Secret:
        def __repr__(self):
            raise AssertionError("repr must never be invoked")
    value, complete = Redactor().capture(Secret())
    assert value == "[UNSUPPORTED:Secret]" and not complete


def test_export_failure_cannot_break_agent():
    class BrokenTransport:
        def submit(self, run):
            raise RuntimeError("offline")
    @trace_agent
    def agent():
        return "still works"
    with Tracer(BrokenTransport()).use():
        assert agent() == "still works"


def test_context_manager_captures_output():
    transport = MemoryTransport()
    tracer = Tracer(transport)
    with tracer.use(), tracer.span("manual-agent", kind="agent", inputs={"x": 1}) as agent:
        with tracer.span("decision", inputs={"x": 1}) as child:
            child["output"] = 2
        agent["output"] = 2
    assert transport.runs[0].output == 2
    assert transport.runs[0].spans[1].kind == "span"


def test_tool_without_agent_is_transparent():
    @trace_tool
    def tool(x):
        return x + 1
    assert tool(1) == 2
