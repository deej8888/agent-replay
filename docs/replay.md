# Deterministic replay contract

## Playback

`POST /v1/runs/{id}/replays` with `{"mode":"playback"}` creates a stored trace copy. New run and span UUIDs preserve original parent relationships, inputs, outputs, errors, timestamps, and durations. `source_run_id` identifies its origin. No code, model, or tool runs. The debugger labels this **Trace playback · no code executed**.

## Re-executing code

Use the same decorated agent and configuration that created the recording:

```python
from pathlib import Path
from agentreplay import MemoryTransport, ReplaySession, Run, Tracer
from agentreplay_examples.agent import shopping_agent

source = Run.model_validate_json(Path("failure.json").read_text())
capture = MemoryTransport()
replay = ReplaySession(source)
try:
    with Tracer(capture).use(), replay:
        shopping_agent("Find a mechanical keyboard under $100", simulate_failure=True)
except ValueError as error:
    print("Recorded failure reproduced:", error)
print(replay.report)
```

`@trace_tool` and `@trace_llm` bind function arguments to named parameters and apply defaults before capture/matching. Positional and keyword calls with equivalent defaults match. JSON key order is irrelevant; JSON primitive types are significant. The engine checks kind, name, sanitized arguments, and the next recorded call position. It returns a deep copy of the stored output. It never invokes the original boundary implementation on either a match or mismatch.

Nested boundary spans are mocked at their outermost tool/LLM boundary. For example, a tool calling a second tool produces both spans while recording; replay returns the outer tool's recorded result and does not execute its body or independently consume its children. Application control flow between boundaries actually runs.

Supported built-in exceptions are recreated from stored type/message. Other exceptions become `RecordedCallError`, since loading arbitrary exception classes would execute untrusted code. A final exception-type/message difference is reported as a divergence. Even built-in exceptions with special formatting (for example `KeyError`) can differ in their rendered message after reconstruction. No traceback locals or executable pickles are stored.

## Fail closed

Unexpected, reordered, renamed or changed calls raise `ReplayDivergence` at the boundary. Missing calls raise on successful context exit and are always included in the report, including when another exception is already propagating. The root trace observer also compares final output, status, and exception with the source. A report can therefore be unfaithful even if every tool call matched.

The SDK installs one Python audit hook on first replay. It checks the active replay context and rejects DNS lookup, socket connection and socket send operations before they run. The hook remains registered but is inert outside replay. It does not patch global socket implementations.

Re-execution is refused for captures containing truncated, unsupported or cyclic values, overlapping sibling boundary calls, or manually authored tool/LLM context spans. A context manager cannot skip its Python body; use decorators for mockable integrations. Custom `kind="span"` decision contexts and `kind="agent"` contexts remain useful for recording.

Reports contain `offline`, `faithful`, `matched_calls`, `total_calls`, `missing_calls`, and `divergences`. A faithfully reproduced recorded failure is still a failed execution with a faithful replay report. A divergence is a different failure and includes the unmatched call position.

## Isolation and limits

This is a deterministic mock layer for trusted instrumented code, not an operating-system sandbox. Decorate every side-effecting integration. The network guard applies to the active Python context: newly created threads without copied context, native extensions, filesystem writes, subprocesses, direct syscalls, and hostile Python code can bypass it. Use a separate network-disabled container/process with filesystem restrictions for code you do not trust. The server only invokes the bundled in-process demo, which has no real integration implementations.

Replay compares sanitized values. Two inputs differing only in redacted secrets intentionally compare equal. A redacted output is returned as its stored redacted representation, which can change downstream behavior and will surface as a mismatch or final-output divergence. Use the same `Redactor` settings on recording and replay; secrets are never recovered. Mutable receivers (`self`/`cls`) are omitted from argument capture, so give methods explicit stable names and represent behaviorally significant state in arguments.

Clock reads, randomness, environment variables, and application/library versions are not virtualized. Record relevant configuration in metadata and inject nondeterministic inputs into decorated boundaries. Re-execution timings describe the new mocked run; playback timings describe the original run.
