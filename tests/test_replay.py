import asyncio
import socket

import pytest
from agentreplay import (
    MemoryTransport,
    ReplayDivergence,
    ReplaySession,
    Tracer,
    trace_agent,
    trace_tool,
)
from agentreplay_examples.agent import shopping_agent


def test_reexecution_never_calls_tool_or_network(recorded, monkeypatch):
    # The original function body is a trap. The recorded boundary must replace it.
    @trace_tool(name="search_catalog")
    def search(request):
        raise AssertionError("External implementation executed")

    @trace_tool(name="check_inventory")
    def inventory(sku, simulate_failure=False):
        socket.create_connection(("example.com", 443))
        raise AssertionError("Network executed")

    from agentreplay_examples import agent

    monkeypatch.setattr(agent, "search_catalog", search)
    monkeypatch.setattr(agent, "check_inventory", inventory)
    monkeypatch.setattr(
        socket, "create_connection", lambda *a, **kw: pytest.fail("Network forbidden")
    )
    transport = MemoryTransport()
    replay = ReplaySession(recorded)
    with Tracer(transport).use(), replay:
        assert shopping_agent("Find a keyboard") == recorded.output
    assert replay.report["faithful"]
    assert replay.report["matched_calls"] == 3


def test_reproduces_recorded_failure():
    transport = MemoryTransport()
    with Tracer(transport).use(), pytest.raises(ValueError):
        shopping_agent("Find a keyboard", True)
    source = transport.runs[0]
    replay = ReplaySession(source)
    with (
        Tracer(MemoryTransport()).use(),
        replay,
        pytest.raises(ValueError, match="missing the required"),
    ):
        shopping_agent("Find a keyboard", True)
    assert replay.report["faithful"]
    assert replay.report["matched_calls"] == 2


def test_mismatch_fails_closed(recorded):
    replay = ReplaySession(recorded)
    with Tracer().use(), pytest.raises(ReplayDivergence, match="matching sanitized input"), replay:
        shopping_agent("A changed request")
    assert replay.report["divergences"]
    assert len(replay.report["missing_calls"]) == 3


def test_missing_calls_are_not_silent(recorded):
    replay = ReplaySession(recorded)
    with pytest.raises(ReplayDivergence, match="Missing"), replay:
        pass
    assert not replay.report["faithful"]


def test_unexpected_call_fails_closed(recorded):
    replay = ReplaySession(recorded)
    with Tracer().use(), pytest.raises(ReplayDivergence, match="exhausted"), replay:
        shopping_agent("Find a keyboard")
        shopping_agent("Find a keyboard")


def test_incomplete_trace_is_rejected(recorded):
    recorded.spans[1].replayable = False
    with pytest.raises(ReplayDivergence, match="truncated"):
        ReplaySession(recorded)


def test_nested_boundaries_are_mocked_at_outer_boundary():
    transport = MemoryTransport()
    calls = []

    @trace_tool
    def inner():
        calls.append("inner")
        return 2

    @trace_tool
    def outer():
        return inner() + 1

    @trace_agent
    def agent():
        return outer()

    with Tracer(transport).use():
        assert agent() == 3
    replay = ReplaySession(transport.runs[0])
    with Tracer().use(), replay:
        assert agent() == 3
    assert calls == ["inner"]
    assert replay.report["total_calls"] == 1


async def test_concurrent_boundary_recording_is_rejected():
    transport = MemoryTransport()

    @trace_tool
    async def tool(x):
        await asyncio.sleep(0.001)
        return x

    @trace_agent
    async def agent():
        return await asyncio.gather(tool(1), tool(2))

    with Tracer(transport).use():
        await agent()
    with pytest.raises(ReplayDivergence, match="Concurrent"):
        ReplaySession(transport.runs[0])


def test_changed_final_output_is_a_divergence(recorded):
    @trace_agent
    def changed_agent():
        shopping_agent("Find a keyboard")
        return "regressed answer"

    replay = ReplaySession(recorded)
    with Tracer().use(), replay:
        changed_agent()
    assert not replay.report["faithful"]


def test_strict_matching_distinguishes_boolean_from_integer():
    transport = MemoryTransport()

    @trace_tool
    def echo(value):
        return value

    @trace_agent
    def agent(value):
        return echo(value)

    with Tracer(transport).use():
        agent(True)
    with Tracer().use(), pytest.raises(ReplayDivergence), ReplaySession(transport.runs[0]):
        agent(1)


def test_uninstrumented_network_is_blocked_in_replay_context(recorded):
    with (
        pytest.raises(ReplayDivergence, match="Network access is forbidden"),
        ReplaySession(recorded),
    ):
        socket.getaddrinfo("example.com", 443)


def test_manual_boundary_context_cannot_claim_to_be_mockable():
    transport = MemoryTransport()
    tracer = Tracer(transport)
    with tracer.use(), tracer.span("agent", kind="agent"):
        with tracer.span("manual-tool", kind="tool"):
            pass
    with pytest.raises(ReplayDivergence, match="unsupported"):
        ReplaySession(transport.runs[0])
