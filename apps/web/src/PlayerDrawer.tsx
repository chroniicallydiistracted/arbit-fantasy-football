import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import type { PlayerFacts } from "./api";
import { points } from "./format";
import { Busy, SourceNote } from "./primitives";
import { useSession } from "./session";
import { http } from "./transport";
export function PlayerDrawer() {
  const [params, setParams] = useSearchParams();
  const player = params.get("player");
  const snapshot = params.get("player_snapshot");
  const query = useQuery({
    queryKey: ["player", player, snapshot],
    queryFn: ({ signal }) =>
      http<PlayerFacts>(
        `/api/v1/players/${encodeURIComponent(player ?? "")}${snapshot ? `?snapshot_id=${encodeURIComponent(snapshot)}` : ""}`,
        { signal },
      ),
    enabled: !!player,
  });
  const dialog = useRef<HTMLDialogElement>(null);
  const { me, save } = useSession();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const close = () => {
    const next = new URLSearchParams(params);
    next.delete("player");
    next.delete("player_snapshot");
    setParams(next, { replace: true });
  };
  useEffect(() => {
    if (!player) return;
    const previous = document.activeElement;
    const panel = dialog.current;
    panel?.showModal();
    setError("");
    return () => {
      panel?.close();
      if (previous instanceof HTMLElement && previous.isConnected) previous.focus();
      else document.getElementById("player-search")?.focus();
    };
  }, [player]);
  if (!player) return null;
  const data = query.data?.player;
  const watched = me?.preferences.watchlist.includes(player) ?? false;
  async function toggle() {
    if (!me) return;
    setSaving(true);
    setError("");
    try {
      await save({
        ...me.preferences,
        watchlist: watched
          ? me.preferences.watchlist.filter((id) => id !== player)
          : [...me.preferences.watchlist, player as string],
      });
    } catch (value) {
      setError(value instanceof Error ? value.message : "Watchlist could not be updated.");
    } finally {
      setSaving(false);
    }
  }
  return (
    <dialog
      className="player-drawer"
      ref={dialog}
      aria-labelledby="player-title"
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
    >
      <div className="drawer-top">
        <span className="eyebrow">Player file</span>
        <button type="button" className="quiet" onClick={close} aria-label="Close player details">
          Close <span aria-hidden="true">×</span>
        </button>
      </div>
      {query.isPending && (
        <>
          <h2 id="player-title">Player details</h2>
          <Busy label="Opening player file…" />
        </>
      )}
      {query.isError && (
        <>
          <h2 id="player-title">Player details unavailable</h2>
          <p role="alert">This player could not be loaded. Close this file and try again.</p>
        </>
      )}
      {data && query.data && (
        <>
          <p className="player-position">
            {data.position}{" "}
            <span> / {data.kind === "defense_unit" ? "Defense & special teams" : "Player"}</span>
          </p>
          <h2 id="player-title">{data.display_name}</h2>
          <button
            type="button"
            className="watch-button"
            aria-pressed={watched}
            disabled={saving}
            onClick={() => void toggle()}
          >
            {saving ? "Saving…" : watched ? "✓ On your watchlist" : "+ Add to watchlist"}
          </button>
          {error && (
            <p role="alert" className="error-text">
              {error}
            </p>
          )}
          <section className="drawer-section">
            <h3>Official points</h3>
            <p className="drawer-points">
              {points(data.official_current_points)} <span>pts</span>
            </p>
            <p className="muted">
              ESPN · scoring period {query.data.snapshot.scoring_period}
              {data.official_current_points === null
                ? " · Total not available"
                : " · Official total"}
            </p>
          </section>
          <section className="drawer-section">
            <h3>Roster facts</h3>
            <dl className="fact-list">
              <div>
                <dt>Availability</dt>
                <dd>
                  {data.availability === "owned"
                    ? "On an FFA roster"
                    : data.availability === "waivers"
                      ? "On waivers"
                      : "Free agent"}
                </dd>
              </div>
              <div>
                <dt>Lineup slot</dt>
                <dd>{data.lineup_slot ?? "Not assigned"}</dd>
              </div>
              <div>
                <dt>Eligible slots</dt>
                <dd>{data.eligible_slots.join(", ") || "Unknown"}</dd>
              </div>
              <div>
                <dt>Health</dt>
                <dd>
                  {data.injury_status ||
                    (data.injured ? "Injury reported" : "No injury flag reported")}
                </dd>
              </div>
              <div>
                <dt>Active</dt>
                <dd>{data.active ? "Listed active" : "Not listed active"}</dd>
              </div>
              <div>
                <dt>Locks</dt>
                <dd>
                  {[
                    data.lineup_locked && "Lineup",
                    data.roster_locked && "Roster",
                    data.trade_locked && "Trade",
                  ]
                    .filter(Boolean)
                    .join(", ") || "None reported"}
                </dd>
              </div>
            </dl>
          </section>
          <section className="analysis-note">
            <p className="eyebrow">Player analysis</p>
            <h3>A fuller picture is coming.</h3>
            <p>
              Evaluations and recommendations will appear once the shared player model has been
              verified.
            </p>
          </section>
          <SourceNote snapshot={query.data.snapshot} />
        </>
      )}
    </dialog>
  );
}
