import { useQueries } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router";
import { AdminAccess } from "./AdminAccess";
import type { PlayerFacts, Preferences } from "./api";
import { Empty, Notice } from "./primitives";
import { useSession } from "./session";
import { http } from "./transport";

export function Settings() {
  const { me, save } = useSession();
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  async function theme(value: Preferences["theme"]) {
    if (!me) return;
    setSaving(true);
    setMessage("");
    try {
      await save({ ...me.preferences, theme: value });
      setFailed(false);
      setMessage("Your appearance preference is saved.");
    } catch (error) {
      setFailed(true);
      setMessage(error instanceof Error ? error.message : "Preference could not be saved.");
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Your account</p>
          <h1>
            Preferences<span className="heading-period">.</span>
          </h1>
        </div>
      </div>
      <section className="settings-section">
        <h2>Appearance</h2>
        <p className="muted">
          Choose the setting that feels right. Your preference follows your account.
        </p>
        <fieldset className="theme-options">
          <legend className="sr-only">Color theme</legend>
          {(["system", "light", "dark"] as const).map((value) => (
            <button
              type="button"
              key={value}
              aria-pressed={me?.preferences.theme === value}
              disabled={saving}
              onClick={() => void theme(value)}
            >
              {value === "system"
                ? "Follow device"
                : value === "light"
                  ? "Warm paper"
                  : "Evening green"}
            </button>
          ))}
        </fieldset>
        {message && <Notice danger={failed}>{message}</Notice>}
      </section>
      <section className="settings-section">
        <h2>Private by design</h2>
        <p>
          Your watchlist and preferences are saved to your account. Private league information is
          held in memory while you use Arbit and cleared when you sign out or go offline.
        </p>
        <p className="muted">
          Arbit uses your approved FFA team assignment. If your assignment needs to change, ask your
          league administrator.
        </p>
      </section>
      {me?.account.role === "admin" && <AdminAccess />}
      <section className="settings-section">
        <h2>Arbit on your home screen</h2>
        <p>
          If your browser supports installation, use its install or Add to Home Screen option.
          Offline access shows a safe connection screen; it does not save your team information.
        </p>
      </section>
    </>
  );
}
export function Watchlist() {
  const { me, save } = useSession();
  const [params, setParams] = useSearchParams();
  const page = Math.max(0, Number.parseInt(params.get("page") ?? "0", 10) || 0);
  const ids = me?.preferences.watchlist ?? [];
  const visible = ids.slice(page * 20, (page + 1) * 20);
  const queries = useQueries({
    queries: visible.map((id) => ({
      queryKey: ["player", id, null],
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        http<PlayerFacts>(`/api/v1/players/${id}`, { signal }),
    })),
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  async function remove(id: string) {
    if (!me) return;
    setSaving(true);
    setError("");
    try {
      await save({ ...me.preferences, watchlist: ids.filter((value) => value !== id) });
    } catch (value) {
      setError(value instanceof Error ? value.message : "Watchlist could not be saved.");
    } finally {
      setSaving(false);
    }
  }
  if (!ids.length)
    return (
      <Empty eyebrow="Your shortlist" title="Keep an eye on a player.">
        <p>
          Find a player using the search above, open their file, and add them to your watchlist.
          Your shortlist is private to you.
        </p>
      </Empty>
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Your shortlist</p>
          <h1>
            Watchlist<span className="heading-period">.</span>
          </h1>
        </div>
        <span className="muted">{ids.length} saved players</span>
      </div>
      {error && <Notice danger>{error}</Notice>}
      <ul className="watchlist">
        {visible.map((id, index) => {
          const query = queries[index];
          return (
            <li key={id}>
              <div>
                <button
                  type="button"
                  className="player-link"
                  disabled={!query.data}
                  onClick={() => {
                    const next = new URLSearchParams(params);
                    next.set("player", id);
                    if (query.data) next.set("player_snapshot", query.data.snapshot.id);
                    setParams(next);
                  }}
                >
                  {query.isPending
                    ? "Loading player…"
                    : (query.data?.player.display_name ?? "Player currently unavailable")}
                </button>
                <p className="muted">
                  {query.data
                    ? `${query.data.player.position} · ${query.data.player.availability === "owned" ? "On an FFA roster" : query.data.player.availability === "waivers" ? "On waivers" : "Free agent"}`
                    : "Saved to your watchlist"}
                </p>
              </div>
              <button
                type="button"
                className="quiet"
                disabled={saving}
                onClick={() => void remove(id)}
                aria-label={`Remove ${query.data?.player.display_name ?? "player"} from watchlist`}
              >
                Remove
              </button>
            </li>
          );
        })}
      </ul>
      {ids.length > 20 && (
        <nav className="pagination" aria-label="Watchlist pages">
          <button
            type="button"
            disabled={page === 0}
            onClick={() => {
              const next = new URLSearchParams(params);
              next.set("page", String(page - 1));
              setParams(next);
            }}
          >
            Previous
          </button>
          <span>
            Page {page + 1} of {Math.ceil(ids.length / 20)}
          </span>
          <button
            type="button"
            disabled={(page + 1) * 20 >= ids.length}
            onClick={() => {
              const next = new URLSearchParams(params);
              next.set("page", String(page + 1));
              setParams(next);
            }}
          >
            Next
          </button>
        </nav>
      )}
    </>
  );
}
