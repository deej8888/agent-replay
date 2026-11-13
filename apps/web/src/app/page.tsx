import { Suspense } from "react";
import { Debugger } from "@/components/debugger";
export default function Page() {
  return (
    <Suspense fallback={<main className="loading">Loading AgentReplay…</main>}>
      <Debugger />
    </Suspense>
  );
}
