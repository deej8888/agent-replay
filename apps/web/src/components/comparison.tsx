"use client";
import Link from "next/link";
import { useState } from "react";
import { ArrowRight, CircleAlert, Columns2, Check } from "lucide-react";
import type { Comparison } from "@/lib/types";
import { duration } from "@/lib/trace";
import { JsonInspector } from "./json-inspector";
import { Status } from "./ui";
export function CompareView({ comparison }: { comparison: Comparison }) {
  const [onlyChanges, setOnlyChanges] = useState(true);
  const changes = comparison.changes.filter(
    (c) => !onlyChanges || c.change !== "unchanged",
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">EXECUTION DIFF</div>
          <h1>Find what changed.</h1>
          <p>Aligned by nested span path and call occurrence.</p>
        </div>
        <span className="duration-delta">
          {comparison.duration_delta_ms >= 0 ? "+" : "−"}
          {duration(Math.abs(comparison.duration_delta_ms))}
        </span>
      </div>
      <div className="compare-grid">
        {[comparison.left, comparison.right].map((run, i) => (
          <section key={`${i}-${run.id}`} className="panel compare-card">
            <div className="panel-title">
              <div>
                <span className="compare-label">{i ? "B" : "A"}</span>
                <h2>{run.name}</h2>
              </div>
              <Status status={run.status} />
            </div>
            <div className="compare-summary">
              <Link href={`/?run=${run.id}`}>
                {run.id.slice(0, 8)} <ArrowRight size={12} />
              </Link>
              <span>
                {duration(run.duration_ms)} · {run.mode}
              </span>
            </div>
            <h3>Input</h3>
            <JsonInspector value={run.input} label="input" />
            <h3>Output</h3>
            <JsonInspector value={run.output} label="output" />
            {run.error && (
              <div className="error-banner">
                <CircleAlert size={16} />
                <p>
                  {run.error.type}: {run.error.message}
                </p>
              </div>
            )}
          </section>
        ))}
      </div>
      <section className="panel diff-panel">
        <div className="panel-title">
          <div>
            <Columns2 size={17} />
            <h2>Span changes</h2>
            <span className="count">
              {
                comparison.changes.filter((c) => c.change !== "unchanged")
                  .length
              }
            </span>
          </div>
          <label className="small muted">
            <input
              type="checkbox"
              checked={onlyChanges}
              onChange={(e) => setOnlyChanges(e.target.checked)}
            />{" "}
            Changed spans only
          </label>
        </div>
        {changes.length === 0 ? (
          <div className="empty compact">
            <Check size={24} />
            <h3>No behavioral differences</h3>
            <p>Inputs, outputs, errors, and metadata match.</p>
          </div>
        ) : (
          changes.map((change) => (
            <details key={change.path} className="diff-row">
              <summary>
                <span className={`diff-badge ${change.change}`}>
                  {change.change}
                </span>
                <code>{change.path}</code>
                <span className="muted small">{change.fields.join(", ")}</span>
              </summary>
              <div className="compare-grid diff-values">
                <div>
                  <h3>Recorded A</h3>
                  <JsonInspector
                    value={
                      change.left
                        ? {
                            input: change.left.input,
                            output: change.left.output,
                            error: change.left.error,
                            metadata: change.left.metadata,
                          }
                        : null
                    }
                  />
                </div>
                <div>
                  <h3>Recorded B</h3>
                  <JsonInspector
                    value={
                      change.right
                        ? {
                            input: change.right.input,
                            output: change.right.output,
                            error: change.right.error,
                            metadata: change.right.metadata,
                          }
                        : null
                    }
                  />
                </div>
              </div>
            </details>
          ))
        )}
      </section>
    </>
  );
}
