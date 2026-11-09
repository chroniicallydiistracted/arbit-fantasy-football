import type { Player } from "./api";

/** Presentation only: all scoring and statistical arithmetic stays on the server. */
export function points(value: string | null | undefined): string {
  if (value == null) return "—";
  const match = /^(-?\d+)(?:\.(\d+))?$/.exec(value);
  if (!match) return value;
  return `${match[1]}.${(match[2] ?? "").padEnd(2, "0")}`;
}
export function record(team: { wins: number; losses: number; ties: number }): string {
  return `${team.wins}–${team.losses}–${team.ties}`;
}
export function ageLabel(observed: string, now = Date.now()): string {
  const age = now - Date.parse(observed);
  if (!Number.isFinite(age)) return "time unknown";
  if (age < 0) return "time unknown";
  if (age < 60_000) return "now";
  if (age < 3_600_000) return `${Math.floor(age / 60_000)} min ago`;
  if (age < 86_400_000) return `${Math.floor(age / 3_600_000)} hr ago`;
  const days = Math.floor(age / 86_400_000);
  return days === 1 ? "1 day ago" : `${days} days ago`;
}
export function dateLabel(observed: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(observed),
  );
}

const INJURY: Record<NonNullable<Player["injury"]>, string> = {
  questionable: "Questionable",
  doubtful: "Doubtful",
  out: "Out",
  injured_reserve: "Injured reserve",
  suspended: "Suspended",
  probable: "Probable",
  day_to_day: "Day to day",
  other: "Injury listed",
};
/** ESPN's injury designation in plain words; the server has already mapped ESPN's codes. */
export function injuryLabel(value: Player["injury"]): string | null {
  return value ? INJURY[value] : null;
}
/** Out, on injured reserve or suspended: not available this week. */
export function injuryRulesOut(value: Player["injury"]): boolean {
  return value === "out" || value === "injured_reserve" || value === "suspended";
}
