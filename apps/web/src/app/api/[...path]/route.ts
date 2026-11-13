import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  if (
    request.method === "POST" &&
    request.headers.get("origin") &&
    new URL(request.headers.get("origin")!).host !== request.headers.get("host")
  ) {
    return Response.json(
      { detail: "Cross-origin writes are disabled" },
      { status: 403 },
    );
  }
  // Fixed upstream and restricted paths prevent an open proxy / arbitrary SSRF.
  if (path[0] !== "v1" || path.some((p) => !/^[a-zA-Z0-9_-]+$/.test(p))) {
    return Response.json({ detail: "Unknown API path" }, { status: 404 });
  }
  try {
    const upstream = (
      process.env.AGENTREPLAY_BACKEND_URL || "http://127.0.0.1:8000"
    ).replace(/\/$/, "");
    const chunks: Uint8Array[] = [];
    let size = 0;
    if (request.body) {
      const reader = request.body.getReader();
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        size += value.length;
        if (size > 2097152) {
          await reader.cancel();
          return Response.json(
            { detail: "Body exceeds 2 MiB" },
            { status: 413 },
          );
        }
        chunks.push(value);
      }
    }
    const response = await fetch(
      `${upstream}/${path.join("/")}${request.nextUrl.search}`,
      {
        method: request.method,
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": process.env.AGENTREPLAY_API_KEY || "",
        },
        body: request.method === "GET" ? undefined : Buffer.concat(chunks),
        signal: AbortSignal.timeout(15000),
        cache: "no-store",
      },
    );
    return new Response(await response.text(), {
      status: response.status,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return Response.json(
      {
        detail:
          "Cannot reach the AgentReplay API. Start the backend on port 8000.",
      },
      { status: 502 },
    );
  }
}
export { proxy as GET, proxy as POST };
