"use client";
import Link from "next/link";
import { useState } from "react";
import {
  Play,
  RefreshCw,
  Clock3,
  GitBranch,
  Box,
  ShieldCheck,
  ArrowRight,
  CircleAlert,
  Workflow,
  Zap,
  Terminal,
  Braces,
} from "lucide-react";
import type { Run, Span } from "@/lib/types";
import {
  duration,
  orderedSpans,
  timestampMs,
  exclusiveLatency,
} from "@/lib/trace";
import { JsonInspector } from "./json-inspector";
import { Status, Timestamp } from "./ui";
export function RunDetail({
  run,
  busy,
  onReplay,
}: {
  run: Run;
  busy: boolean;
  onReplay: (mode: string, diverge?: boolean) => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected =
    run.spans.find((s) => s.id === selectedId) ||
    run.spans.find((s) => s.status === "error" && s.kind !== "agent") ||
    run.spans[0];
  const breakdown = exclusiveLatency(run.spans);
  const total = Object.values(breakdown).reduce((a, b) => a + b, 0) || 1;
  const canExecute =
    run.metadata.replay_target === "shopping-demo" &&
    run.mode !== "reexecution";
  return (
    <>
      <div className="page-heading detail-heading">
        <div>
          <div className="eyebrow">EXECUTION / {run.id.slice(0, 8)}</div>
          <h1>
            {run.name} <Status status={run.status} />
          </h1>
          <p>
            <Timestamp value={run.started_at} />{" "}
            <span className="separator">/</span>{" "}
            <span className="mono">{run.id}</span>
          </p>
        </div>
        <div className="heading-actions">
          <button
            className="button secondary"
            disabled={busy}
            onClick={() => onReplay("playback")}
          >
            <Play size={14} />
            View playback
          </button>
          {canExecute && (
            <button
              className="button primary"
              disabled={busy}
              onClick={() => onReplay("reexecution")}
            >
              <RefreshCw size={14} />
              Re-execute offline
            </button>
          )}
        </div>
      </div>
      <div className="detail-metrics">
        <span>
          <Clock3 size={15} />
          <strong>{duration(run.duration_ms)}</strong>total duration
        </span>
        <span>
          <GitBranch size={15} />
          <strong>{run.spans.length}</strong>spans
        </span>
        <span>
          <Box size={15} />
          {String(run.metadata.model || "No model")}
        </span>
        <span className="mode-tag">
          <ShieldCheck size={15} />
          {run.mode === "record"
            ? "Recorded execution"
            : run.mode === "playback"
              ? "Trace playback · no code executed"
              : "Offline re-execution · recorded responses"}
        </span>
      </div>
      {run.source_run_id && (
        <div className="source-line">
          Derived from{" "}
          <Link href={`/?run=${run.source_run_id}`}>
            {run.source_run_id.slice(0, 8)} <ArrowRight size={12} />
          </Link>
          {run.mode === "playback" && (
            <span>Original timestamps and durations are preserved.</span>
          )}
        </div>
      )}
      {run.replay_report && (
        <section
          className={`replay-notice ${run.replay_report.faithful ? "faithful" : "diverged"}`}
        >
          <ShieldCheck size={19} />
          <div>
            <strong>
              {run.mode === "playback"
                ? "Faithful trace playback"
                : run.replay_report.faithful
                  ? "All recorded calls matched"
                  : "Replay divergence detected"}
            </strong>
            <p>
              {run.mode === "playback"
                ? "This is a copy of the recorded trace. Application code was not executed."
                : `${run.replay_report.matched_calls} / ${run.replay_report.total_calls} calls matched. Tool and model implementations were bypassed.`}
            </p>
            {!run.replay_report.faithful && (
              <JsonInspector value={run.replay_report} label="Replay report" />
            )}
          </div>
        </section>
      )}
      {run.error && (
        <div className="error-banner">
          <CircleAlert size={18} />
          <div>
            <strong>{run.error.type}</strong>
            <p>{run.error.message}</p>
          </div>
        </div>
      )}
      <div className="debugger-grid">
        <section className="panel timeline-panel">
          <div className="panel-title">
            <div>
              <Workflow size={17} />
              <h2>Execution timeline</h2>
              <span className="count">{run.spans.length}</span>
            </div>
            <span className="muted small">Click a step to inspect</span>
          </div>
          <div className="timeline-axis">
            <span>STEP</span>
            <span>RELATIVE DURATION</span>
          </div>
          <div className="timeline-rows">
            {orderedSpans(run.spans).map(({ span, depth }) => {
              const left = Math.max(
                0,
                ((timestampMs(span.started_at) - timestampMs(run.started_at)) /
                  Math.max(run.duration_ms, 0.001)) *
                  100,
              );
              const width = Math.min(
                100 - left,
                Math.max(
                  2,
                  (span.duration_ms / Math.max(run.duration_ms, 0.001)) * 100,
                ),
              );
              return (
                <button
                  key={span.id}
                  onClick={() => setSelectedId(span.id)}
                  className={`timeline-row ${selected.id === span.id ? "current" : ""} ${span.status === "error" ? "failed-step" : ""}`}
                  aria-pressed={selected.id === span.id}
                >
                  <div
                    className="step-name"
                    style={{ paddingLeft: 16 + depth * 20 }}
                  >
                    <span className={`kind-icon ${span.kind}`}>
                      {span.kind === "llm" ? (
                        <Zap size={14} />
                      ) : span.kind === "tool" ? (
                        <Terminal size={14} />
                      ) : (
                        <Workflow size={14} />
                      )}
                    </span>
                    <span>
                      <strong>{span.name}</strong>
                      <small>
                        {span.kind}
                        {span.status === "error" ? " · failed" : ""}
                      </small>
                    </span>
                  </div>
                  <div className="bar-track">
                    <span
                      className={`span-bar ${span.kind} ${span.status === "error" ? "error" : ""}`}
                      style={{
                        marginLeft: `${Math.min(left, 98)}%`,
                        width: `${Math.max(1, width)}%`,
                      }}
                    />
                  </div>
                  <span className="span-duration">
                    {duration(span.duration_ms)}
                  </span>
                </button>
              );
            })}
          </div>
          <div className="latency-breakdown">
            <h3>
              Latency breakdown <span className="muted">exclusive time</span>
            </h3>
            <div className="breakdown-track">
              {Object.entries(breakdown).map(([kind, ms]) => (
                <span
                  key={kind}
                  className={kind}
                  style={{ width: `${(ms / total) * 100}%` }}
                />
              ))}
            </div>
            <div className="breakdown-legend">
              {Object.entries(breakdown).map(([kind, ms]) => (
                <span key={kind}>
                  <i className={kind} />
                  {kind}
                  <strong>{duration(ms)}</strong>
                </span>
              ))}
            </div>
          </div>
        </section>
        <SpanInspector span={selected} />
      </div>
      <section className="panel metadata-panel">
        <div className="panel-title">
          <div>
            <Braces size={16} />
            <h2>Execution metadata</h2>
          </div>
        </div>
        <div className="metadata-body">
          <JsonInspector value={run.metadata} label="metadata" />
          <div>
            <h3>Agent input</h3>
            <JsonInspector value={run.input} label="input" />
          </div>
          <div>
            <h3>Final output</h3>
            <JsonInspector value={run.output} label="output" />
          </div>
        </div>
      </section>
      {canExecute && (
        <div className="divergence-demo">
          <span>
            <GitBranch size={16} />
            Test strict matching by changing the request before replay.
          </span>
          <button
            className="text-button"
            disabled={busy}
            onClick={() => onReplay("reexecution", true)}
          >
            Simulate divergence <ArrowRight size={13} />
          </button>
        </div>
      )}
    </>
  );
}

function SpanInspector({ span }: { span: Span }) {
  const [tab, setTab] = useState("input");
  return (
    <section className="panel inspector">
      <div className="panel-title">
        <div>
          <Braces size={17} />
          <h2>Span inspector</h2>
        </div>
        <span className={`kind-label ${span.kind}`}>{span.kind}</span>
      </div>
      <div className="inspector-heading">
        <h3>{span.name}</h3>
        <div>
          <Status status={span.status} />
          <span className="mono muted">{duration(span.duration_ms)}</span>
        </div>
      </div>
      <div role="tablist" aria-label="Span details" className="inspector-tabs">
        {["input", "output", "error", "metadata"].map((name) => (
          <button
            key={name}
            role="tab"
            aria-selected={tab === name}
            onClick={() => setTab(name)}
          >
            {name}
            {name === "error" && span.error && <span className="error-dot" />}
          </button>
        ))}
      </div>
      <div role="tabpanel" className="json-panel">
        <JsonInspector
          value={
            tab === "input"
              ? span.input
              : tab === "output"
                ? span.output
                : tab === "error"
                  ? span.error
                  : span.metadata
          }
          label={tab}
        />
      </div>
      <div className="inspector-footer">
        <ShieldCheck size={13} />
        {span.replayable
          ? "Captured and sanitized"
          : "Capture incomplete · not replayable"}
      </div>
    </section>
  );
}
