"use client";
import type { Json } from "@/lib/types";

export function JsonInspector({ value, label = "value", depth = 0 }: { value: Json; label?: string; depth?: number }) {
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value);
    return <details className="json-node" open={depth < 1}>
      <summary><span className="json-key">{label}</span> <span className="muted">{Array.isArray(value) ? `[${entries.length} items]` : `{${entries.length} keys}`}</span></summary>
      <div className="json-children">{entries.map(([key, child]) => <JsonInspector key={key} label={key} value={child} depth={depth + 1} />)}</div>
    </details>;
  }
  return <div className="json-leaf"><span className="json-key">{label}: </span><span className={typeof value === "string" ? "json-string" : "json-primitive"}>{JSON.stringify(value)}</span></div>;
}
