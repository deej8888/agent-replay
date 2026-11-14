import argparse
from pathlib import Path

from pydantic import ValidationError

from .models import Run
from .regression import MAX_RECORDING_BYTES, export_regression
from .replay import ReplayDivergence


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentReplay developer tools")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export-test", help="Export an offline pytest regression bundle")
    export.add_argument("recording", type=Path, help="A recorded AgentReplay run JSON file")
    export.add_argument(
        "--entrypoint", help="Importable Python target, for example my_package.agent:run_agent"
    )
    export.add_argument("--output", type=Path, required=True, help="Destination ZIP file")
    args = parser.parse_args()
    try:
        with args.recording.open("rb") as recording:
            data = recording.read(MAX_RECORDING_BYTES + 1)
        if len(data) > MAX_RECORDING_BYTES:
            raise ValueError("Recording exceeds 2 MiB")
        source = Run.model_validate_json(data)
        bundle = export_regression(source, args.entrypoint)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(bundle)
    except ValidationError:
        parser.exit(2, "Export failed: invalid AgentReplay recording\n")
    except (OSError, ValueError, ReplayDivergence) as exc:
        parser.exit(2, f"Export failed: {exc}\n")
    print(f"Saved offline pytest regression bundle to {args.output}")


if __name__ == "__main__":
    main()
