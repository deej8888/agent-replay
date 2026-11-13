from uuid import uuid4

from agentreplay import MemoryTransport, ReplayDivergence, ReplaySession, Run, Tracer
from agentreplay_examples.agent import shopping_agent
from sqlalchemy.orm import Session

from .database import RunRow, SpanRow


def store_run(db: Session, run: Run) -> Run:
    payload = run.model_dump(mode="json")
    model = run.metadata.get("model")
    db.add(RunRow(id=str(run.id), name=run.name, status=run.status, started_at=run.started_at, duration_ms=run.duration_ms, mode=run.mode, source_run_id=str(run.source_run_id) if run.source_run_id else None, model=str(model)[:200] if model else None, payload={k: v for k, v in payload.items() if k != "spans"}))
    db.flush()
    db.add_all([SpanRow(id=str(s.id), run_id=str(run.id), parent_id=str(s.parent_id) if s.parent_id else None, sequence=s.sequence, name=s.name, kind=s.kind, payload=s.model_dump(mode="json")) for s in run.spans])
    db.commit()
    return run


def load_run(db: Session, run_id: str) -> Run | None:
    from sqlalchemy import select
    row = db.get(RunRow, run_id)
    if row is None:
        return None
    spans = db.scalars(select(SpanRow).where(SpanRow.run_id == run_id).order_by(SpanRow.sequence)).all()
    return Run.model_validate({**row.payload, "spans": [s.payload for s in spans]})


def playback(source: Run) -> Run:
    ids = {s.id: uuid4() for s in source.spans}
    return source.model_copy(update={"id": uuid4(), "source_run_id": source.id, "mode": "playback", "spans": [s.model_copy(update={"id": ids[s.id], "parent_id": ids.get(s.parent_id) if s.parent_id else None}) for s in source.spans], "replay_report": {"offline": True, "faithful": True, "description": "Stored trace playback. No application code was executed.", "divergences": [], "missing_calls": []}}, deep=True)


def reexecute(source: Run, diverge: bool = False) -> Run:
    if source.metadata.get("replay_target") != "shopping-demo" or source.name != "shopping-assistant":
        raise ValueError("Server re-execution supports only the bundled shopping-demo; use the SDK for your own code")
    if not isinstance(source.input, dict) or set(source.input) != {"request", "simulate_failure"}:
        raise ValueError("Invalid shopping-demo input")
    if not isinstance(source.input["request"], str) or not isinstance(source.input["simulate_failure"], bool):
        raise ValueError("Invalid shopping-demo input types")
    replay = ReplaySession(source)
    transport = MemoryTransport()
    inputs = dict(source.input)
    if diverge:
        inputs["request"] = str(inputs["request"]) + " (changed during replay)"
    try:
        with Tracer(transport).use(), replay:
            shopping_agent(**inputs)
    except Exception:
        pass  # The instrumented run retains the exact failure for the debugger.
    if not transport.runs:
        raise ReplayDivergence("Re-execution produced no trace")
    result = transport.runs[0]
    report = replay.report
    # Calls may match while application logic or final output diverges.
    if result.output != source.output or result.status != source.status or result.error != source.error:
        divergences = report["divergences"]
        assert isinstance(divergences, list)
        divergences.append({"message": "Final output, status, or exception differs from the recording"})
        report["faithful"] = False
    return result.model_copy(update={"mode": "reexecution", "source_run_id": source.id, "replay_report": report})
