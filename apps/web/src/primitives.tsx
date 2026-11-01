import type { ReactNode } from "react";
import type { Snapshot } from "./api";
import { ageLabel, dateLabel } from "./format";
export function Arrow({ direction = "right" }: { direction?: "right" | "up" }) {
  return (
    <svg className="arrow" aria-hidden="true" viewBox="0 0 24 24" fill="none">
      <path
        d={direction === "up" ? "M5 19 19 5M5 5h14v14" : "M4 12h15m-6-6 6 6-6 6"}
        stroke="currentColor"
        strokeWidth="1.6"
      />
    </svg>
  );
}
export function Busy({ label = "Opening your front office…" }: { label?: string }) {
  return (
    <div className="busy" role="status">
      <span className="loading-line" />
      {label}
    </div>
  );
}
export function Notice({
  children,
  action,
  danger = false,
}: {
  children: ReactNode;
  action?: ReactNode;
  danger?: boolean;
}) {
  return (
    <div className={`notice ${danger ? "notice-danger" : ""}`} role={danger ? "alert" : "status"}>
      <div>{children}</div>
      {action}
    </div>
  );
}
export function SourceNote({ snapshot, failed = false }: { snapshot: Snapshot; failed?: boolean }) {
  const status = failed
    ? "Refresh unavailable"
    : snapshot.stale || snapshot.source_status !== "fresh"
      ? "Needs a refresh"
      : "Latest saved view";
  return (
    <div className={`source-note ${failed || snapshot.stale ? "source-stale" : ""}`}>
      <span className="status-dot" aria-hidden="true" />
      <span>{status}</span>
      <span className="source-time">
        ESPN ·{" "}
        <time dateTime={snapshot.observed_at} title={dateLabel(snapshot.observed_at)}>
          {ageLabel(snapshot.observed_at)}
        </time>
      </span>
    </div>
  );
}
export function Empty({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="empty-state">
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <div className="empty-copy">{children}</div>
    </section>
  );
}
