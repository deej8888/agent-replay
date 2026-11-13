import { describe, expect, it } from "vitest";
import { duration, exclusiveLatency, orderedSpans, timestampMs } from "./trace";
import type { Span } from "./types";

const span = (
  id: string,
  parent: string | null,
  sequence: number,
  start: number,
  end: number,
  kind: Span["kind"] = "tool",
): Span => ({
  id,
  parent_id: parent,
  sequence,
  name: id,
  kind,
  started_at: new Date(start).toISOString(),
  ended_at: new Date(end).toISOString(),
  duration_ms: end - start,
  input: null,
  output: null,
  error: null,
  metadata: {},
  replayable: true,
  status: "success",
});

describe("trace rendering", () => {
  it("retains submillisecond positions for fast deterministic tools", () => {
    expect(
      timestampMs("2026-01-01T00:00:00.000600Z") -
        timestampMs("2026-01-01T00:00:00.000100Z"),
    ).toBeCloseTo(0.5, 2);
  });
  it("places children under their parents instead of completion order", () => {
    const spans = [
      span("child", "root", 1, 10, 40),
      span("root", null, 0, 0, 100, "agent"),
      span("nested", "child", 2, 15, 25),
    ];
    expect(orderedSpans(spans).map((x) => [x.span.id, x.depth])).toEqual([
      ["root", 0],
      ["child", 1],
      ["nested", 2],
    ]);
  });
  it("does not double count overlapping children in exclusive latency", () => {
    const values = exclusiveLatency([
      span("root", null, 0, 0, 100, "agent"),
      span("a", "root", 1, 10, 50),
      span("b", "root", 2, 30, 70),
    ]);
    expect(values.agent).toBe(40);
    expect(values.tool).toBe(80);
  });
  it("formats short and long durations", () => {
    expect(duration(0.123)).toBe("0.12 ms");
    expect(duration(2100)).toBe("2.10 s");
  });
});
