import Link from "next/link";
import { Workflow, Box, ChevronRight } from "lucide-react";
import type { RunSummary } from "@/lib/types";
import { duration } from "@/lib/trace";
import { Status, Timestamp } from "./ui";
export function ExecutionRow({
  run,
  checked,
  onSelect,
}: {
  run: RunSummary;
  checked: boolean;
  onSelect: () => void;
}) {
  return (
    <tr className={checked ? "selected-row" : ""}>
      <td>
        <input
          type="checkbox"
          aria-label={`Select ${run.id}`}
          checked={checked}
          onChange={onSelect}
        />
      </td>
      <td>
        <Link href={`/?run=${run.id}`} className="execution-name">
          <span className={`run-icon ${run.status}`}>
            <Workflow size={16} />
          </span>
          <span>
            <strong>{run.name}</strong>
            <small>
              {run.id.slice(0, 8)}{" "}
              <span>· {run.mode === "record" ? "recorded" : run.mode}</span>
            </small>
          </span>
        </Link>
        {run.error && (
          <div className="row-error" title={run.error.message}>
            {run.error.type}: {run.error.message}
          </div>
        )}
      </td>
      <td>
        <Status status={run.status} />
      </td>
      <td className="mono">{duration(run.duration_ms)}</td>
      <td>
        <span className="model-tag">
          <Box size={12} />
          {String(run.metadata.model || "—")}
        </span>
      </td>
      <td className="muted small">
        <Timestamp value={run.started_at} />
      </td>
      <td>
        <Link aria-label={`Inspect ${run.id}`} href={`/?run=${run.id}`}>
          <ChevronRight size={16} />
        </Link>
      </td>
    </tr>
  );
}
