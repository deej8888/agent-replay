"use client";

import { useState } from "react";
import { Download, FileCode2, LoaderCircle } from "lucide-react";
import { regressionBundle } from "@/lib/api";
import type { Run } from "@/lib/types";

export function RegressionExport({ run }: { run: Run }) {
  const [open, setOpen] = useState(false);
  const [entrypoint, setEntrypoint] = useState(
    typeof run.metadata.entrypoint === "string"
      ? run.metadata.entrypoint
      : run.metadata.replay_target === "shopping-demo"
        ? "agentreplay_examples.agent:shopping_agent"
        : "",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [downloaded, setDownloaded] = useState(false);
  const unavailable =
    run.replay_report?.faithful === false
      ? "Open the source recording to export a test for this diverged replay."
      : run.metadata.concurrent
        ? "Concurrent calls cannot be replayed deterministically. Export a sequential recording."
        : run.spans.some((span) => !span.replayable)
          ? "This trace contains incomplete or unsupported values. Record complete values before exporting a test."
          : "";

  async function download(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setDownloaded(false);
    try {
      const bundle = await regressionBundle(run.id, entrypoint.trim());
      const url = URL.createObjectURL(bundle);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `agentreplay-regression-${run.id.replaceAll("-", "").slice(0, 12)}.zip`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setDownloaded(true);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="panel regression-export"
      aria-labelledby="regression-export-title"
    >
      <div className="panel-title">
        <div>
          <FileCode2 size={17} />
          <h2 id="regression-export-title">Regression test</h2>
        </div>
        <button
          className="button secondary"
          aria-expanded={open}
          aria-controls="regression-export-form"
          onClick={() => setOpen((value) => !value)}
        >
          <Download size={14} />
          {open ? "Close export" : "Export pytest"}
        </button>
      </div>
      {open && (
        <div id="regression-export-form" className="regression-export-body">
          {unavailable ? (
            <p className="muted" role="status">
              {unavailable}
            </p>
          ) : (
            <form onSubmit={download}>
              <p>
                The bundle includes the recording and a pytest test that checks
                calls, output, and errors through offline replay.
              </p>
              {run.error && (
                <p className="expected-error">
                  This test expects the recorded {run.error.type}. It passes
                  when that failure is reproduced.
                </p>
              )}
              <label htmlFor="regression-entrypoint">Python entrypoint</label>
              <div className="regression-export-fields">
                <input
                  id="regression-entrypoint"
                  required
                  maxLength={500}
                  value={entrypoint}
                  onChange={(event) => {
                    setEntrypoint(event.target.value);
                    setDownloaded(false);
                  }}
                  placeholder="my_package.agent:run_agent"
                  aria-describedby="regression-entrypoint-help"
                  spellCheck={false}
                  autoComplete="off"
                />
                <button
                  className="button primary"
                  type="submit"
                  disabled={busy || !entrypoint.trim()}
                >
                  {busy ? (
                    <LoaderCircle size={14} className="spin" />
                  ) : (
                    <Download size={14} />
                  )}
                  Download test bundle
                </button>
              </div>
              <p id="regression-entrypoint-help" className="muted small">
                Use an importable decorated agent or adapter in your Python
                environment. The bundle includes setup instructions.
              </p>
              {error && (
                <p className="red" role="alert">
                  {error}
                </p>
              )}
              {downloaded && (
                <p className="teal" role="status">
                  Test bundle downloaded. Unzip it and follow the included
                  README to run pytest.
                </p>
              )}
            </form>
          )}
        </div>
      )}
    </section>
  );
}
