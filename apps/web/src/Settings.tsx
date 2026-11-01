import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router";
import { AdminAccess } from "./AdminAccess";
import type { PlayerFacts, Preferences } from "./api";
import { ageLabel } from "./format";
import type { components } from "./generated/api";
import { Notice, PageTitle, StatePanel } from "./primitives";
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
      setMessage("Saved.");
    } catch (error) {
      setFailed(true);
      setMessage(error instanceof Error ? error.message : "Saving failed. Try again.");
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      <PageTitle title="Preferences" />
      <div className="settings">
        <section className="settings-section">
          <h2>Appearance</h2>
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
                {value === "system" ? "System" : value === "light" ? "Light" : "Dark"}
              </button>
            ))}
          </fieldset>
          {message && <Notice danger={failed}>{message}</Notice>}
        </section>
        <Devices />
        <section className="settings-section">
          <h2>Data on this device</h2>
          <p>
            League data is held in memory and cleared when you sign out or go offline. Your
            watchlist and preferences are saved to your account.
          </p>
          <p className="muted">
            Your team is assigned by the league administrator. Ask them if it needs to change.
          </p>
        </section>
        {me?.account.role === "admin" && <AdminAccess />}
        <section className="settings-section">
          <h2>Install</h2>
          <p>
            Use your browser’s Install or Add to Home Screen option. Offline, Arbit shows a
            connection notice and no team data.
          </p>
        </section>
      </div>
    </>
  );
}
function Devices() {
  const { auth, refresh } = useSession();
  const query = useQuery({
    queryKey: ["sessions"],
    queryFn: ({ signal }) =>
      http<components["schemas"]["DeviceSessions"]>("/api/v1/me/sessions", { signal }),
  });
  const [error, setError] = useState("");
  async function end(id: string, current: boolean) {
    setError("");
    try {
      await http("/api/v1/me/sessions/revoke", {
        method: "POST",
        body: { session_id: id },
        csrf: auth?.csrf_token,
      });
      if (current) await refresh();
      else await query.refetch();
    } catch (value) {
      setError(value instanceof Error ? value.message : "That device couldn’t be signed out.");
    }
  }
  return (
    <section className="settings-section">
      <h2>Signed-in devices</h2>
      {error && <Notice danger>{error}</Notice>}
      {query.isError && <Notice danger>Devices couldn’t be loaded.</Notice>}
      <ul className="device-list">
        {query.data?.sessions.map((session) => (
          <li key={session.id}>
            <span>
              <strong>{session.device ?? "Unknown device"}</strong>
              {session.current && " · This device"}
              <span className="player-line">Last used {ageLabel(session.last_seen_at)}</span>
            </span>
            <button
              type="button"
              aria-label={`End session on ${session.device ?? "unknown device"}`}
              onClick={() => void end(session.id, session.current)}
            >
              End session
            </button>
          </li>
        ))}
      </ul>
      <p className="muted">Sessions end after 30 days without use, and always after 90 days.</p>
    </section>
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
      setError(value instanceof Error ? value.message : "Watchlist update failed.");
    } finally {
      setSaving(false);
    }
  }
  if (!ids.length)
    return (
      <StatePanel title="Watchlist is empty">
        <p>Search for a player, open them, and choose Add to watchlist.</p>
      </StatePanel>
    );
  return (
    <>
      <PageTitle title="Watchlist">
        <span className="muted">{ids.length} players</span>
      </PageTitle>
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
                    ? "Loading…"
                    : (query.data?.player.display_name ?? "Player unavailable")}
                </button>
                <p className="muted">
                  {query.data
                    ? `${query.data.player.position} · ${query.data.player.availability === "owned" ? "On an FFA roster" : query.data.player.availability === "waivers" ? "On waivers" : "Free agent"}`
                    : "On watchlist"}
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
