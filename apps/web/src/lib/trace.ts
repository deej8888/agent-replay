import type { Span } from "./types";

export function duration(ms: number): string {
  return ms >= 1000
    ? `${(ms / 1000).toFixed(2)} s`
    : `${ms.toFixed(ms < 10 ? 2 : 0)} ms`;
}

export function orderedSpans(spans: Span[]): { span: Span; depth: number }[] {
  const children = new Map<string | null, Span[]>();
  for (const span of spans)
    children.set(span.parent_id, [
      ...(children.get(span.parent_id) || []),
      span,
    ]);
  const result: { span: Span; depth: number }[] = [];
  const visit = (parent: string | null, depth: number) => {
    for (const span of (children.get(parent) || []).sort(
      (a, b) => a.sequence - b.sequence,
    )) {
      result.push({ span, depth });
      visit(span.id, depth + 1);
    }
  };
  visit(null, 0);
  return result;
}

export function exclusiveLatency(spans: Span[]): Record<string, number> {
  const result: Record<string, number> = {};
  for (const span of spans) {
    const intervals = spans
      .filter((s) => s.parent_id === span.id)
      .map((s) => [Date.parse(s.started_at), Date.parse(s.ended_at)])
      .sort((a, b) => a[0] - b[0]);
    let covered = 0,
      end = -Infinity;
    for (const [start, stop] of intervals) {
      covered += Math.max(0, stop - Math.max(start, end));
      end = Math.max(end, stop);
    }
    // Use proportional wall-clock coverage to retain submillisecond precision.
    const wall = Date.parse(span.ended_at) - Date.parse(span.started_at);
    const own =
      wall > 0
        ? span.duration_ms * Math.max(0, 1 - covered / wall)
        : Math.max(
            0,
            span.duration_ms -
              spans
                .filter((s) => s.parent_id === span.id)
                .reduce((a, b) => a + b.duration_ms, 0),
          );
    result[span.kind] = (result[span.kind] || 0) + own;
  }
  return result;
}
