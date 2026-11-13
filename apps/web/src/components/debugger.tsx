"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Activity, ArrowLeft, ArrowRight, Box, Braces, Check, ChevronRight, CircleAlert, Clock3, Code2, Columns2, Command, Database, GitBranch, LayoutDashboard, LoaderCircle, Play, RefreshCw, Search, ShieldCheck, Terminal, Workflow, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { duration, exclusiveLatency, orderedSpans } from "@/lib/trace";
import type { Comparison, Run, RunList, RunSummary, Span } from "@/lib/types";
import { JsonInspector } from "./json-inspector";

function Status({ status }: { status: string }) {
  return <span className={`status ${status}`}><span className="status-dot" />{status === "success" ? "Success" : "Failed"}</span>;
}
function Timestamp({ value }: { value: string }) {
  const display = new Date(value).toLocaleString("en-US", { timeZone: "UTC", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" }) + " UTC";
  return <time dateTime={value} title={value}>{display}</time>;
}

export function Debugger() {
  const params = useSearchParams();
  const router = useRouter();
  const runId = params.get("run"), left = params.get("left"), right = params.get("right");
  const view = params.get("view") || "overview";
  const [list, setList] = useState<RunList>({ items: [], total: 0, offset: 0, limit: 50 });
  const [run, setRun] = useState<Run | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [mode, setMode] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [demoRequest, setDemoRequest] = useState("Find a mechanical keyboard under $100");
  const refresh = useCallback(() => setRevision(n => n + 1), []);

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      setLoading(true); setError(""); setRun(null); setComparison(null);
      const query = new URLSearchParams({ q, limit: "50", offset: String(offset) });
      if (status) query.set("status", status);
      if (mode) query.set("mode", mode);
      const load = runId ? api<Run>(`/runs/${runId}`).then(value => { if (active) setRun(value); }) : left && right ? api<Comparison>(`/compare?left=${left}&right=${right}`).then(value => { if (active) setComparison(value); }) : api<RunList>(`/runs?${query}`).then(value => { if (active) setList(value); });
      load.catch(e => { if (active) setError(String(e.message)); }).finally(() => { if (active) setLoading(false); });
    }, 180);
    return () => { active = false; clearTimeout(timer); };
  }, [runId, left, right, q, status, mode, offset, revision]);

  async function createDemo(fail: boolean) {
    setBusy(true); setError("");
    try {
      const created = await api<Run>("/demo", { request: demoRequest, fail });
      router.push(`/?run=${created.id}`); refresh();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function replay(replayMode: string, diverge = false) {
    if (!run) return;
    setBusy(true); setError("");
    try {
      const created = await api<Run>(`/runs/${run.id}/replays`, { mode: replayMode, simulate_divergence: diverge });
      router.push(`/?run=${created.id}`); refresh();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  const isDetail = !!runId, isCompare = !!left || view === "compare";
  const totalErrors = list.items.filter(r => r.status === "error").length;
  const mean = list.items.length ? list.items.reduce((n, r) => n + r.duration_ms, 0) / list.items.length : 0;
  const success = list.items.length ? Math.round(100 * (list.items.length - totalErrors) / list.items.length) : null;

  return <div className="app-shell">
    <aside className="sidebar">
      <Link href="/" className="brand"><span className="brand-mark"><Workflow size={22} /></span>AgentReplay<span className="version">Î±</span></Link>
      <div className="workspace"><span className="workspace-icon"><Terminal size={16} /></span><div>Local workspace<small>Development</small></div><span className="online-dot" /></div>
      <div className="nav-caption">WORKSPACE</div>
      <nav aria-label="Main navigation">
        <Link href="/" className={!isDetail && !isCompare && view === "overview" ? "active" : ""}><LayoutDashboard size={17} />Overview</Link>
        <Link href="/?view=executions" className={isDetail || view === "executions" ? "active" : ""}><Activity size={17} />Executions</Link>
        <Link href="/?view=compare" className={isCompare ? "active" : ""}><Columns2 size={17} />Compare runs</Link>
      </nav>
      <div className="sidebar-bottom"><div className="local-card"><ShieldCheck size={17} /><strong>Local by default</strong><p>Your traces stay in your database. Replay uses recorded responses.</p></div><a href="https://github.com/deej8888/agent-replay" target="_blank" rel="noreferrer"><Code2 size={16} />Open source <ArrowRight size={14} /></a><span className="sidebar-version">AgentReplay v0.1.0 <span>MIT</span></span></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div><span className="muted">Workspace</span><ChevronRight size={13} /><span>{isDetail ? "Execution details" : isCompare ? "Compare runs" : view === "executions" ? "Executions" : "Overview"}</span></div><span className="environment"><span className="online-dot" />LOCAL DEVELOPMENT</span></header>
      <main>
        {error && <div className="alert" role="alert"><CircleAlert size={18} /><span>{error}</span><button onClick={refresh}>Retry</button></div>}
        {isDetail ? <>
          <Link href="/?view=executions" className="back"><ArrowLeft size={14} />All executions</Link>
          {loading ? <Loading /> : run && <RunDetail run={run} busy={busy} onReplay={replay} />}
        </> : left && right ? <>
          <Link href="/?view=compare" className="back"><ArrowLeft size={14} />Choose executions</Link>
          {loading ? <Loading /> : comparison && <CompareView comparison={comparison} />}
        </> : <>
          <div className="page-heading"><div><div className="eyebrow">AGENT OBSERVABILITY</div><h1>{isCompare ? "Compare executions" : view === "executions" ? "Executions" : "Your agents, under the hood."}</h1><p>{isCompare ? "Select two runs to inspect changes in inputs, responses, and behavior." : "Follow every decision. Find the failure. Replay with confidence."}</p></div><button className="button secondary" onClick={refresh} disabled={loading}><RefreshCw size={15} className={loading ? "spin" : ""} />Refresh</button></div>
          {view === "overview" && !isCompare && <>
            <div className="stats"><Stat label="Recorded executions" value={String(list.total)} icon={<Activity size={17} />} detail="Matching all current filters" /><Stat label="Success rate" value={success === null ? "â€”" : `${success}%`} icon={<Check size={17} />} detail={`Across ${list.items.length} displayed runs`} green /><Stat label="Average duration" value={list.items.length ? duration(mean) : "â€”"} icon={<Clock3 size={17} />} detail="Across displayed runs" /><Stat label="Failed executions" value={String(totalErrors)} icon={<CircleAlert size={17} />} detail="In the current page" red={totalErrors > 0} /></div>
            <section className="demo-banner"><div className="demo-symbol"><Workflow size={27} /></div><div className="demo-copy"><div className="inline-title">Meet your first trace <span className="tiny-tag">NO API KEY NEEDED</span></div><p>Run the shopping agent with two tools and a deterministic model.</p><label className="sr-only" htmlFor="demo-request">Demo request</label><input id="demo-request" value={demoRequest} onChange={e => setDemoRequest(e.target.value)} maxLength={2000} /></div><div className="demo-actions"><button className="button primary" disabled={busy || !demoRequest.trim()} onClick={() => createDemo(false)}><Play size={14} />Run demo agent</button><button className="text-button" disabled={busy || !demoRequest.trim()} onClick={() => createDemo(true)}>Record a failure <ArrowRight size={13} /></button></div></section>
          </>}
          <section className="panel executions-panel"><div className="panel-title"><div><Activity size={17} /><h2>{isCompare ? "Choose two executions" : "Recent executions"}</h2><span className="count">{list.total}</span></div><span className="muted small">{selected.length} selected {selected.length > 0 && <button className="text-button" onClick={() => setSelected([])}>Clear</button>}</span></div>
            <div className="filters"><div className="search"><Search size={16} /><input aria-label="Search executions" placeholder="Search by agent name or run IDâ€¦" value={q} onChange={e => { setQ(e.target.value); setOffset(0); }} /></div><select aria-label="Filter status" value={status} onChange={e => { setStatus(e.target.value); setOffset(0); }}><option value="">All statuses</option><option value="success">Success</option><option value="error">Failed</option></select><select aria-label="Filter mode" value={mode} onChange={e => { setMode(e.target.value); setOffset(0); }}><option value="">All modes</option><option value="record">Recorded</option><option value="playback">Playback</option><option value="reexecution">Re-execution</option></select><button className="button secondary" disabled={selected.length !== 2} onClick={() => router.push(`/?left=${selected[0]}&right=${selected[1]}`)}><Columns2 size={14} />Compare {selected.length ? `(${selected.length}/2)` : ""}</button></div>
            {loading ? <Loading /> : list.items.length ? <div className="table-scroll"><table><thead><tr><th className="checkbox-col"><span className="sr-only">Select</span></th><th>EXECUTION</th><th>STATUS</th><th>DURATION</th><th>MODEL</th><th>STARTED</th><th /></tr></thead><tbody>{list.items.map(item => <ExecutionRow key={item.id} run={item} checked={selected.includes(item.id)} onSelect={() => setSelected(values => values.includes(item.id) ? values.filter(v => v !== item.id) : values.length < 2 ? [...values, item.id] : [values[1], item.id])} />)}</tbody></table></div> : <div className="empty"><Database size={30} /><h3>{q || status || mode ? "No matching executions" : "Your first trace starts here"}</h3><p>{q || status || mode ? "Adjust the filters to find your runs." : "Run the demo above, or connect your Python agent with the SDK."}</p></div>}
            <div className="table-footer"><span>Showing {list.items.length ? offset + 1 : 0}â€“{offset + list.items.length} of {list.total} executions</span><div><button aria-label="Previous page" disabled={!offset || loading} onClick={() => setOffset(v => Math.max(0, v - 50))}><ArrowLeft size={14} /></button><button aria-label="Next page" disabled={offset + list.items.length >= list.total || loading} onClick={() => setOffset(v => v + 50)}><ArrowRight size={14} /></button></div></div>
          </section>
          <div className="below-table"><span><Command size={13} />Built for the moments when â€œit worked yesterdayâ€ isnâ€™t enough.</span><span>Python SDK Â· FastAPI Â· SQLite / PostgreSQL</span></div>
          {view === "overview" && !isCompare && <section className="integration"><div><div className="eyebrow">A FEW LINES. THE WHOLE PICTURE.</div><h2>Bring your own agent.</h2><p>Capture tools, model calls, and the decisions in between.</p></div><pre><code><span className="code-purple">from</span> agentreplay <span className="code-purple">import</span> trace_agent, trace_tool, Tracer{`\n\n`}<span className="code-teal">@trace_agent</span>{`\ndef my_agent(request: str):\n    return search(request)`}</code></pre><Link href="https://github.com/deej8888/agent-replay#instrument-your-agent" target="_blank" className="text-button">SDK integration <ArrowRight size={14} /></Link></section>}
        </>}
      </main>
      <footer><span><span className="brand-dot" />AgentReplay</span><span>Understand every step.</span><span>Open source, always.</span></footer>
    </div>
  </div>;
}

function Loading() { return <div className="loading" role="status"><LoaderCircle size={20} className="spin" />Loading tracesâ€¦</div>; }
function Stat({ label, value, icon, detail, green, red }: { label: string; value: string; icon: React.ReactNode; detail: string; green?: boolean; red?: boolean }) {
  return <div className="stat"><div className="stat-label">{label}<span>{icon}</span></div><strong className={green ? "teal" : red ? "red" : ""}>{value}</strong><small>{detail}</small></div>;
}
function ExecutionRow({ run, checked, onSelect }: { run: RunSummary; checked: boolean; onSelect: () => void }) {
  return <tr className={checked ? "selected-row" : ""}><td><input type="checkbox" aria-label={`Select ${run.id}`} checked={checked} onChange={onSelect} /></td><td><Link href={`/?run=${run.id}`} className="execution-name"><span className={`run-icon ${run.status}`}><Workflow size={16} /></span><span><strong>{run.name}</strong><small>{run.id.slice(0, 8)} <span>Â· {run.mode === "record" ? "recorded" : run.mode}</span></small></span></Link>{run.error && <div className="row-error" title={run.error.message}>{run.error.type}: {run.error.message}</div>}</td><td><Status status={run.status} /></td><td className="mono">{duration(run.duration_ms)}</td><td><span className="model-tag"><Box size={12} />{String(run.metadata.model || "â€”")}</span></td><td className="muted small"><Timestamp value={run.started_at} /></td><td><Link aria-label={`Inspect ${run.id}`} href={`/?run=${run.id}`}><ChevronRight size={16} /></Link></td></tr>;
}

function RunDetail({ run, busy, onReplay }: { run: Run; busy: boolean; onReplay: (mode: string, diverge?: boolean) => void }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = run.spans.find(s => s.id === selectedId) || run.spans.find(s => s.status === "error" && s.kind !== "agent") || run.spans[0];
  const breakdown = exclusiveLatency(run.spans);
  const total = Object.values(breakdown).reduce((a, b) => a + b, 0) || 1;
  const canExecute = run.metadata.replay_target === "shopping-demo" && run.mode !== "reexecution";
  return <>
    <div className="page-heading detail-heading"><div><div className="eyebrow">EXECUTION / {run.id.slice(0, 8)}</div><h1>{run.name} <Status status={run.status} /></h1><p><Timestamp value={run.started_at} /> <span className="separator">/</span> <span className="mono">{run.id}</span></p></div><div className="heading-actions"><button className="button secondary" disabled={busy} onClick={() => onReplay("playback")}><Play size={14} />View playback</button>{canExecute && <button className="button primary" disabled={busy} onClick={() => onReplay("reexecution")}><RefreshCw size={14} />Re-execute offline</button>}</div></div>
    <div className="detail-metrics"><span><Clock3 size={15} /><strong>{duration(run.duration_ms)}</strong>total duration</span><span><GitBranch size={15} /><strong>{run.spans.length}</strong>spans</span><span><Box size={15} />{String(run.metadata.model || "No model")}</span><span className="mode-tag"><ShieldCheck size={15} />{run.mode === "record" ? "Recorded execution" : run.mode === "playback" ? "Trace playback Â· no code executed" : "Offline re-execution Â· recorded responses"}</span></div>
    {run.source_run_id && <div className="source-line">Derived from <Link href={`/?run=${run.source_run_id}`}>{run.source_run_id.slice(0, 8)} <ArrowRight size={12} /></Link>{run.mode === "playback" && <span>Original timestamps and durations are preserved.</span>}</div>}
    {run.replay_report && <section className={`replay-notice ${run.replay_report.faithful ? "faithful" : "diverged"}`}><ShieldCheck size={19} /><div><strong>{run.mode === "playback" ? "Faithful trace playback" : run.replay_report.faithful ? "All recorded calls matched" : "Replay divergence detected"}</strong><p>{run.mode === "playback" ? "This is a copy of the recorded trace. Application code was not executed." : `${run.replay_report.matched_calls} / ${run.replay_report.total_calls} calls matched. Tool and model implementations were bypassed.`}</p>{!run.replay_report.faithful && <JsonInspector value={run.replay_report} label="Replay report" />}</div></section>}
    {run.error && <div className="error-banner"><CircleAlert size={18} /><div><strong>{run.error.type}</strong><p>{run.error.message}</p></div></div>}
    <div className="debugger-grid"><section className="panel timeline-panel"><div className="panel-title"><div><Workflow size={17} /><h2>Execution timeline</h2><span className="count">{run.spans.length}</span></div><span className="muted small">Click a step to inspect</span></div><div className="timeline-axis"><span>STEP</span><span>RELATIVE DURATION</span></div><div className="timeline-rows">{orderedSpans(run.spans).map(({ span, depth }) => {
      const left = Math.max(0, (Date.parse(span.started_at) - Date.parse(run.started_at)) / Math.max(run.duration_ms, 0.001) * 100);
      const width = Math.min(100 - left, Math.max(2, span.duration_ms / Math.max(run.duration_ms, 0.001) * 100));
      return <button key={span.id} onClick={() => setSelectedId(span.id)} className={`timeline-row ${selected.id === span.id ? "current" : ""} ${span.status === "error" ? "failed-step" : ""}`} aria-pressed={selected.id === span.id}><div className="step-name" style={{ paddingLeft: 16 + depth * 20 }}><span className={`kind-icon ${span.kind}`}>{span.kind === "llm" ? <Zap size={14} /> : span.kind === "tool" ? <Terminal size={14} /> : <Workflow size={14} />}</span><span><strong>{span.name}</strong><small>{span.kind}{span.status === "error" ? " Â· failed" : ""}</small></span></div><div className="bar-track"><span className={`span-bar ${span.kind} ${span.status === "error" ? "error" : ""}`} style={{ marginLeft: `${Math.min(left, 98)}%`, width: `${Math.max(1, width)}%` }} /></div><span className="span-duration">{duration(span.duration_ms)}</span></button>;
    })}</div><div className="latency-breakdown"><h3>Latency breakdown <span className="muted">exclusive time</span></h3><div className="breakdown-track">{Object.entries(breakdown).map(([kind, ms]) => <span key={kind} className={kind} style={{ width: `${ms / total * 100}%` }} />)}</div><div className="breakdown-legend">{Object.entries(breakdown).map(([kind, ms]) => <span key={kind}><i className={kind} />{kind}<strong>{duration(ms)}</strong></span>)}</div></div></section><SpanInspector span={selected} /></div>
    <section className="panel metadata-panel"><div className="panel-title"><div><Braces size={16} /><h2>Execution metadata</h2></div></div><div className="metadata-body"><JsonInspector value={run.metadata} label="metadata" /><div><h3>Agent input</h3><JsonInspector value={run.input} label="input" /></div><div><h3>Final output</h3><JsonInspector value={run.output} label="output" /></div></div></section>
    {canExecute && <div className="divergence-demo"><span><GitBranch size={16} />Test strict matching by changing the request before replay.</span><button className="text-button" disabled={busy} onClick={() => onReplay("reexecution", true)}>Simulate divergence <ArrowRight size={13} /></button></div>}
  </>;
}

function SpanInspector({ span }: { span: Span }) {
  const [tab, setTab] = useState("input");
  return <section className="panel inspector"><div className="panel-title"><div><Braces size={17} /><h2>Span inspector</h2></div><span className={`kind-label ${span.kind}`}>{span.kind}</span></div><div className="inspector-heading"><h3>{span.name}</h3><div><Status status={span.status} /><span className="mono muted">{duration(span.duration_ms)}</span></div></div><div role="tablist" aria-label="Span details" className="inspector-tabs">{["input", "output", "error", "metadata"].map(name => <button key={name} role="tab" aria-selected={tab === name} onClick={() => setTab(name)}>{name}{name === "error" && span.error && <span className="error-dot" />}</button>)}</div><div role="tabpanel" className="json-panel"><JsonInspector value={tab === "input" ? span.input : tab === "output" ? span.output : tab === "error" ? span.error : span.metadata} label={tab} /></div><div className="inspector-footer"><ShieldCheck size={13} />{span.replayable ? "Captured and sanitized" : "Capture incomplete Â· not replayable"}</div></section>;
}

function CompareView({ comparison }: { comparison: Comparison }) {
  const [onlyChanges, setOnlyChanges] = useState(true);
  const changes = comparison.changes.filter(c => !onlyChanges || c.change !== "unchanged");
  return <><div className="page-heading"><div><div className="eyebrow">EXECUTION DIFF</div><h1>Find what changed.</h1><p>Aligned by nested span path and call occurrence.</p></div><span className="duration-delta">{comparison.duration_delta_ms >= 0 ? "+" : "âˆ’"}{duration(Math.abs(comparison.duration_delta_ms))}</span></div><div className="compare-grid">{[comparison.left, comparison.right].map((run, i) => <section key={`${i}-${run.id}`} className="panel compare-card"><div className="panel-title"><div><span className="compare-label">{i ? "B" : "A"}</span><h2>{run.name}</h2></div><Status status={run.status} /></div><div className="compare-summary"><Link href={`/?run=${run.id}`}>{run.id.slice(0, 8)} <ArrowRight size={12} /></Link><span>{duration(run.duration_ms)} Â· {run.mode}</span></div><h3>Input</h3><JsonInspector value={run.input} label="input" /><h3>Output</h3><JsonInspector value={run.output} label="output" />{run.error && <div className="error-banner"><CircleAlert size={16} /><p>{run.error.type}: {run.error.message}</p></div>}</section>)}</div><section className="panel diff-panel"><div className="panel-title"><div><Columns2 size={17} /><h2>Span changes</h2><span className="count">{comparison.changes.filter(c => c.change !== "unchanged").length}</span></div><label className="small muted"><input type="checkbox" checked={onlyChanges} onChange={e => setOnlyChanges(e.target.checked)} /> Changed spans only</label></div>{changes.length === 0 ? <div className="empty compact"><Check size={24} /><h3>No behavioral differences</h3><p>Inputs, outputs, errors, and metadata match.</p></div> : changes.map(change => <details key={change.path} className="diff-row"><summary><span className={`diff-badge ${change.change}`}>{change.change}</span><code>{change.path}</code><span className="muted small">{change.fields.join(", ")}</span></summary><div className="compare-grid diff-values"><div><h3>Recorded A</h3><JsonInspector value={change.left ? { input: change.left.input, output: change.left.output, error: change.left.error, metadata: change.left.metadata } : null} /></div><div><h3>Recorded B</h3><JsonInspector value={change.right ? { input: change.right.input, output: change.right.output, error: change.right.error, metadata: change.right.metadata } : null} /></div></div></details>)}</section></>;
}

