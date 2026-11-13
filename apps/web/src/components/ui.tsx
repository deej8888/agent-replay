"use client";
import { LoaderCircle } from "lucide-react";
export function Status({ status }: { status: string }) {
  return (
    <span className={`status ${status}`}>
      <span className="status-dot" />
      {status === "success" ? "Success" : "Failed"}
    </span>
  );
}
export function Timestamp({ value }: { value: string }) {
  const display =
    new Date(value).toLocaleString("en-US", {
      timeZone: "UTC",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }) + " UTC";
  return (
    <time dateTime={value} title={value}>
      {display}
    </time>
  );
}

export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle size={20} className="spin" />
      Loading traces…
    </div>
  );
}
export function Stat({
  label,
  value,
  icon,
  detail,
  green,
  red,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  detail: string;
  green?: boolean;
  red?: boolean;
}) {
  return (
    <div className="stat">
      <div className="stat-label">
        {label}
        <span>{icon}</span>
      </div>
      <strong className={green ? "teal" : red ? "red" : ""}>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}
