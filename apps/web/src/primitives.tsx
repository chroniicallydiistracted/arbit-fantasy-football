import type { ReactNode } from "react";
import type { Snapshot } from "./api";
import { ageLabel, dateLabel } from "./format";

export function Arrow({ direction = "right" }: { direction?: "right" | "up" }) {
  return (
    <svg width="14" height="14" aria-hidden="true" viewBox="0 0 24 24" fill="none">
      <path
        d={direction === "up" ? "M5 19 19 5M5 5h14v14" : "M4 12h15m-6-6 6 6-6 6"}
        stroke="currentColor"
        strokeWidth="2.4"
      />
    </svg>
  );
}
export function Busy({ label = "Loading league data…" }: { label?: string }) {
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
export type SourceState = "current" | "behind" | "down";
export function sourceState(snapshot: Snapshot, failed = false): SourceState {
  if (failed) return "down";
  return snapshot.stale || snapshot.source_status !== "fresh" ? "behind" : "current";
}
export function SourceNote({ snapshot, failed = false }: { snapshot: Snapshot; failed?: boolean }) {
  const state = sourceState(snapshot, failed);
  return (
    <span className="status" data-state={state}>
      <span>
        {state === "down" ? "Refresh failed" : state === "behind" ? "Behind" : "Current"} · ESPN{" "}
        <time dateTime={snapshot.observed_at} title={dateLabel(snapshot.observed_at)}>
          {ageLabel(snapshot.observed_at)}
        </time>
      </span>
    </span>
  );
}
/** Page title with the hash-mark rule beneath it. */
export function PageTitle({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <>
      <div className="page-head">
        <h1>{title}</h1>
        {children}
      </div>
      <div className="hash-rule" aria-hidden="true" />
    </>
  );
}
export function StatePanel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <>
      <PageTitle title={title} />
      <section className="state-panel">{children}</section>
    </>
  );
}
