"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronRight,
  CircleAlert,
  Clock3,
  Code2,
  Columns2,
  Command,
  Database,
  LayoutDashboard,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  Terminal,
  Workflow,
} from "lucide-react";
import { api } from "@/lib/api";
import { duration } from "@/lib/trace";
import type { Comparison, Run, RunList } from "@/lib/types";
import { Loading, Stat } from "./ui";
import { RunDetail } from "./run-detail";
import { CompareView } from "./comparison";
import { ExecutionRow } from "./execution-row";
export function Debugger() {
  const params = useSearchParams();
  const router = useRouter();
  const runId = params.get("run"),
    left = params.get("left"),
    right = params.get("right");
  const view = params.get("view") || "overview";
  const [list, setList] = useState<RunList>({
    items: [],
    total: 0,
    offset: 0,
    limit: 50,
  });
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
  const [demoRequest, setDemoRequest] = useState(
    "Find a mechanical keyboard under $100",
  );
  const refresh = useCallback(() => setRevision((n) => n + 1), []);

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      setLoading(true);
      setError("");
      setRun(null);
      setComparison(null);
      const query = new URLSearchParams({
        q,
        limit: "50",
        offset: String(offset),
      });
      if (status) query.set("status", status);
      if (mode) query.set("mode", mode);
      const load = runId
        ? api<Run>(`/runs/${runId}`).then((value) => {
            if (active) setRun(value);
          })
        : left && right
          ? api<Comparison>(`/compare?left=${left}&right=${right}`).then(
              (value) => {
                if (active) setComparison(value);
              },
            )
          : api<RunList>(`/runs?${query}`).then((value) => {
              if (active) setList(value);
            });
      load
        .catch((e) => {
          if (active) setError(String(e.message));
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 180);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [runId, left, right, q, status, mode, offset, revision]);

  async function createDemo(fail: boolean) {
    setBusy(true);
    setError("");
    try {
      const created = await api<Run>("/demo", { request: demoRequest, fail });
      router.push(`/?run=${created.id}`);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function replay(replayMode: string, diverge = false) {
    if (!run) return;
    setBusy(true);
    setError("");
    try {
      const created = await api<Run>(`/runs/${run.id}/replays`, {
        mode: replayMode,
        simulate_divergence: diverge,
      });
      router.push(`/?run=${created.id}`);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const isDetail = !!runId,
    isCompare = !!left || view === "compare";
  const totalErrors = list.items.filter((r) => r.status === "error").length;
  const mean = list.items.length
    ? list.items.reduce((n, r) => n + r.duration_ms, 0) / list.items.length
    : 0;
  const success = list.items.length
    ? Math.round((100 * (list.items.length - totalErrors)) / list.items.length)
    : null;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/" className="brand">
          <span className="brand-mark">
            <Workflow size={22} />
          </span>
          AgentReplay<span className="version">α</span>
        </Link>
        <div className="workspace">
          <span className="workspace-icon">
            <Terminal size={16} />
          </span>
          <div>
            Local workspace<small>Development</small>
          </div>
          <span className="online-dot" />
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <Link
            href="/"
            className={
              !isDetail && !isCompare && view === "overview" ? "active" : ""
            }
          >
            <LayoutDashboard size={17} />
            Overview
          </Link>
          <Link
            href="/?view=executions"
            className={isDetail || view === "executions" ? "active" : ""}
          >
            <Activity size={17} />
            Executions
          </Link>
          <Link href="/?view=compare" className={isCompare ? "active" : ""}>
            <Columns2 size={17} />
            Compare runs
          </Link>
        </nav>
        <div className="sidebar-bottom">
          <div className="local-card">
            <ShieldCheck size={17} />
            <strong>Local by default</strong>
            <p>
              Your traces stay in your database. Replay uses recorded responses.
            </p>
          </div>
          <a
            href="https://github.com/deej8888/agent-replay"
            target="_blank"
            rel="noreferrer"
          >
            <Code2 size={16} />
            Open source <ArrowRight size={14} />
          </a>
          <span className="sidebar-version">
            AgentReplay v0.1.0 <span>MIT</span>
          </span>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <span className="muted">Workspace</span>
            <ChevronRight size={13} />
            <span>
              {isDetail
                ? "Execution details"
                : isCompare
                  ? "Compare runs"
                  : view === "executions"
                    ? "Executions"
                    : "Overview"}
            </span>
          </div>
          <span className="environment">
            <span className="online-dot" />
            LOCAL DEVELOPMENT
          </span>
        </header>
        <main>
          {error && (
            <div className="alert" role="alert">
              <CircleAlert size={18} />
              <span>{error}</span>
              <button onClick={refresh}>Retry</button>
            </div>
          )}
          {isDetail ? (
            <>
              <Link href="/?view=executions" className="back">
                <ArrowLeft size={14} />
                All executions
              </Link>
              {loading ? (
                <Loading />
              ) : (
                run && <RunDetail run={run} busy={busy} onReplay={replay} />
              )}
            </>
          ) : left && right ? (
            <>
              <Link href="/?view=compare" className="back">
                <ArrowLeft size={14} />
                Choose executions
              </Link>
              {loading ? (
                <Loading />
              ) : (
                comparison && <CompareView comparison={comparison} />
              )}
            </>
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">AGENT OBSERVABILITY</div>
                  <h1>
                    {isCompare
                      ? "Compare executions"
                      : view === "executions"
                        ? "Executions"
                        : "Your agents, under the hood."}
                  </h1>
                  <p>
                    {isCompare
                      ? "Select two runs to inspect changes in inputs, responses, and behavior."
                      : "Follow every decision. Find the failure. Replay with confidence."}
                  </p>
                </div>
                <button
                  className="button secondary"
                  onClick={refresh}
                  disabled={loading}
                >
                  <RefreshCw size={15} className={loading ? "spin" : ""} />
                  Refresh
                </button>
              </div>
              {view === "overview" && !isCompare && (
                <>
                  <div className="stats">
                    <Stat
                      label="Recorded executions"
                      value={String(list.total)}
                      icon={<Activity size={17} />}
                      detail="Matching all current filters"
                    />
                    <Stat
                      label="Success rate"
                      value={success === null ? "—" : `${success}%`}
                      icon={<Check size={17} />}
                      detail={`Across ${list.items.length} displayed runs`}
                      green
                    />
                    <Stat
                      label="Average duration"
                      value={list.items.length ? duration(mean) : "—"}
                      icon={<Clock3 size={17} />}
                      detail="Across displayed runs"
                    />
                    <Stat
                      label="Failed executions"
                      value={String(totalErrors)}
                      icon={<CircleAlert size={17} />}
                      detail="In the current page"
                      red={totalErrors > 0}
                    />
                  </div>
                  <section className="demo-banner">
                    <div className="demo-symbol">
                      <Workflow size={27} />
                    </div>
                    <div className="demo-copy">
                      <div className="inline-title">
                        Meet your first trace{" "}
                        <span className="tiny-tag">NO API KEY NEEDED</span>
                      </div>
                      <p>
                        Run the shopping agent with two tools and a
                        deterministic model.
                      </p>
                      <label className="sr-only" htmlFor="demo-request">
                        Demo request
                      </label>
                      <input
                        id="demo-request"
                        value={demoRequest}
                        onChange={(e) => setDemoRequest(e.target.value)}
                        maxLength={2000}
                      />
                    </div>
                    <div className="demo-actions">
                      <button
                        className="button primary"
                        disabled={busy || !demoRequest.trim()}
                        onClick={() => createDemo(false)}
                      >
                        <Play size={14} />
                        Run demo agent
                      </button>
                      <button
                        className="text-button"
                        disabled={busy || !demoRequest.trim()}
                        onClick={() => createDemo(true)}
                      >
                        Record a failure <ArrowRight size={13} />
                      </button>
                    </div>
                  </section>
                </>
              )}
              <section className="panel executions-panel">
                <div className="panel-title">
                  <div>
                    <Activity size={17} />
                    <h2>
                      {isCompare
                        ? "Choose two executions"
                        : "Recent executions"}
                    </h2>
                    <span className="count">{list.total}</span>
                  </div>
                  <span className="muted small">
                    {selected.length} selected{" "}
                    {selected.length > 0 && (
                      <button
                        className="text-button"
                        onClick={() => setSelected([])}
                      >
                        Clear
                      </button>
                    )}
                  </span>
                </div>
                <div className="filters">
                  <div className="search">
                    <Search size={16} />
                    <input
                      aria-label="Search executions"
                      placeholder="Search by agent name or run ID…"
                      value={q}
                      onChange={(e) => {
                        setQ(e.target.value);
                        setOffset(0);
                      }}
                    />
                  </div>
                  <select
                    aria-label="Filter status"
                    value={status}
                    onChange={(e) => {
                      setStatus(e.target.value);
                      setOffset(0);
                    }}
                  >
                    <option value="">All statuses</option>
                    <option value="success">Success</option>
                    <option value="error">Failed</option>
                  </select>
                  <select
                    aria-label="Filter mode"
                    value={mode}
                    onChange={(e) => {
                      setMode(e.target.value);
                      setOffset(0);
                    }}
                  >
                    <option value="">All modes</option>
                    <option value="record">Recorded</option>
                    <option value="playback">Playback</option>
                    <option value="reexecution">Re-execution</option>
                  </select>
                  <button
                    className="button secondary"
                    disabled={selected.length !== 2}
                    onClick={() =>
                      router.push(`/?left=${selected[0]}&right=${selected[1]}`)
                    }
                  >
                    <Columns2 size={14} />
                    Compare {selected.length ? `(${selected.length}/2)` : ""}
                  </button>
                </div>
                {loading ? (
                  <Loading />
                ) : list.items.length ? (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th className="checkbox-col">
                            <span className="sr-only">Select</span>
                          </th>
                          <th>EXECUTION</th>
                          <th>STATUS</th>
                          <th>DURATION</th>
                          <th>MODEL</th>
                          <th>STARTED</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {list.items.map((item) => (
                          <ExecutionRow
                            key={item.id}
                            run={item}
                            checked={selected.includes(item.id)}
                            onSelect={() =>
                              setSelected((values) =>
                                values.includes(item.id)
                                  ? values.filter((v) => v !== item.id)
                                  : values.length < 2
                                    ? [...values, item.id]
                                    : [values[1], item.id],
                              )
                            }
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty">
                    <Database size={30} />
                    <h3>
                      {q || status || mode
                        ? "No matching executions"
                        : "Your first trace starts here"}
                    </h3>
                    <p>
                      {q || status || mode
                        ? "Adjust the filters to find your runs."
                        : "Run the demo above, or connect your Python agent with the SDK."}
                    </p>
                  </div>
                )}
                <div className="table-footer">
                  <span>
                    Showing {list.items.length ? offset + 1 : 0}–
                    {offset + list.items.length} of {list.total} executions
                  </span>
                  <div>
                    <button
                      aria-label="Previous page"
                      disabled={!offset || loading}
                      onClick={() => setOffset((v) => Math.max(0, v - 50))}
                    >
                      <ArrowLeft size={14} />
                    </button>
                    <button
                      aria-label="Next page"
                      disabled={
                        offset + list.items.length >= list.total || loading
                      }
                      onClick={() => setOffset((v) => v + 50)}
                    >
                      <ArrowRight size={14} />
                    </button>
                  </div>
                </div>
              </section>
              <div className="below-table">
                <span>
                  <Command size={13} />
                  Built for the moments when “it worked yesterday” isn’t enough.
                </span>
                <span>Python SDK · FastAPI · SQLite / PostgreSQL</span>
              </div>
              {view === "overview" && !isCompare && (
                <section className="integration">
                  <div>
                    <div className="eyebrow">
                      A FEW LINES. THE WHOLE PICTURE.
                    </div>
                    <h2>Bring your own agent.</h2>
                    <p>
                      Capture tools, model calls, and the decisions in between.
                    </p>
                  </div>
                  <pre>
                    <code>
                      <span className="code-purple">from</span> agentreplay{" "}
                      <span className="code-purple">import</span> trace_agent,
                      trace_tool, Tracer{`\n\n`}
                      <span className="code-teal">@trace_agent</span>
                      {`\ndef my_agent(request: str):\n    return search(request)`}
                    </code>
                  </pre>
                  <Link
                    href="https://github.com/deej8888/agent-replay#instrument-your-agent"
                    target="_blank"
                    className="text-button"
                  >
                    SDK integration <ArrowRight size={14} />
                  </Link>
                </section>
              )}
            </>
          )}
        </main>
        <footer>
          <span>
            <span className="brand-dot" />
            AgentReplay
          </span>
          <span>Understand every step.</span>
          <span>Open source, always.</span>
        </footer>
      </div>
    </div>
  );
}
