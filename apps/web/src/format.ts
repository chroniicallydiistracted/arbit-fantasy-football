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
  if (!Number.isFinite(age)) return "Time unavailable";
  if (age < 0) return "Time needs verification";
  if (age < 60_000) return "Just now";
  if (age < 3_600_000) return `${Math.floor(age / 60_000)} min ago`;
  if (age < 86_400_000) return `${Math.floor(age / 3_600_000)} hr ago`;
  return `${Math.floor(age / 86_400_000)} days ago`;
}
export function dateLabel(observed: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(observed),
  );
}
