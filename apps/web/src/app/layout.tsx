import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentReplay · Agent execution debugger",
  description: "Record, inspect, and deterministically replay your AI agents.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
