import { spawn } from "node:child_process";
const index = process.argv.indexOf("--port");
const child = spawn(process.execPath, [".next/standalone/server.js"], {
  stdio: "inherit",
  env: {
    ...process.env,
    HOSTNAME: process.env.AGENTREPLAY_WEB_HOST || "127.0.0.1",
    PORT: index >= 0 ? process.argv[index + 1] : process.env.PORT || "3000",
  },
});
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => child.kill(signal));
child.on("exit", (code) => process.exit(code ?? 0));
