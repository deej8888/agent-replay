export type Json =
  null | boolean | number | string | Json[] | { [key: string]: Json };
export interface Span {
  id: string;
  parent_id: string | null;
  name: string;
  kind: "agent" | "tool" | "llm" | "span";
  sequence: number;
  started_at: string;
  ended_at: string;
  duration_ms: number;
  status: "success" | "error";
  input: Json;
  output: Json;
  error: { type: string; message: string } | null;
  metadata: Record<string, Json>;
  replayable: boolean;
}
export interface Run {
  id: string;
  name: string;
  started_at: string;
  ended_at: string;
  duration_ms: number;
  status: "success" | "error";
  input: Json;
  output: Json;
  error: Span["error"];
  metadata: Record<string, Json>;
  spans: Span[];
  mode: "record" | "playback" | "reexecution";
  source_run_id: string | null;
  replay_report: Record<string, Json> | null;
}
export type RunSummary = Omit<Run, "spans">;
export interface RunList {
  items: RunSummary[];
  total: number;
  limit: number;
  offset: number;
}
export interface Comparison {
  left: Run;
  right: Run;
  duration_delta_ms: number;
  changes: {
    path: string;
    change: string;
    fields: string[];
    left: Span | null;
    right: Span | null;
    duration_delta_ms: number;
  }[];
}
