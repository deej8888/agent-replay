import argparse
import json
from pathlib import Path

from agentreplay import BufferedHTTPTransport, MemoryTransport, ReplaySession, Run, Tracer

from .agent import shopping_agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Record or replay the no-key shopping agent")
    parser.add_argument("--fail", action="store_true")
    parser.add_argument("--request", default="Find a mechanical keyboard under $100")
    parser.add_argument("--output", type=Path, default=Path("demo-run.json"))
    parser.add_argument("--replay", type=Path, help="Re-execute using only responses in this recording")
    parser.add_argument("--submit", action="store_true", help="Submit recording to the local API")
    args = parser.parse_args()
    memory = MemoryTransport()
    if args.replay:
        source = Run.model_validate_json(args.replay.read_text(encoding="utf-8"))
        inputs = source.input
        if not isinstance(inputs, dict):
            parser.error("Recording has invalid agent input")
        session = ReplaySession(source)
        try:
            with Tracer(memory).use(), session:
                print(shopping_agent(**inputs))
        except Exception as exc:
            print(f"Reproduced: {type(exc).__name__}: {exc}")
        print(json.dumps(session.report, indent=2))
        return
    with Tracer(memory).use():
        try:
            print(shopping_agent(args.request, args.fail))
        except ValueError as exc:
            print(f"Recorded failure: {exc}")
    run = memory.runs[0]
    args.output.write_text(run.model_dump_json(indent=2), encoding="utf-8")
    print(f"Saved {run.id} to {args.output}")
    if args.submit:
        with BufferedHTTPTransport() as transport:
            transport.submit(run)
        if transport.failed:
            raise SystemExit("Trace submission failed; is the API running?")


if __name__ == "__main__":
    main()
