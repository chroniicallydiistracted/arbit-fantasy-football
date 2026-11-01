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
      setError(value instanceof Error ? value.message : "Watchlist update failed.");
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
      <div className="drawer-head">
        <div className="drawer-top">
          <span>Player</span>
          <button type="button" className="quiet" onClick={close} aria-label="Close player details">
            Close
          </button>
        </div>
        {data && query.data ? (
          <>
            <p>
              {data.position} ·{" "}
              {data.kind === "defense_unit" ? "Defense & special teams" : "Athlete"}
            </p>
            <h2 id="player-title">{data.display_name}</h2>
          </>
        ) : (
          <h2 id="player-title">{query.isError ? "Player unavailable" : "Player"}</h2>
        )}
      </div>
      <div className="drawer-body">
        {query.isPending && <Busy label="Loading player…" />}
        {query.isError && (
          <p role="alert">This player couldn’t be loaded. Close this and try again.</p>
        )}
        {data && query.data && (
          <>
            <button
              type="button"
              className="toggle"
              aria-pressed={watched}
              disabled={saving}
              onClick={() => void toggle()}
            >
              {saving ? "Saving…" : watched ? "On watchlist" : "Add to watchlist"}
            </button>
            {error && (
              <p role="alert" className="error-text">
                {error}
              </p>
            )}
            <section>
              <p className="drawer-points">{points(data.official_current_points)}</p>
              <p className="fine">
                Official ESPN points, scoring period {query.data.snapshot.scoring_period}
                {data.official_current_points === null ? ". No score yet." : ""}
              </p>
            </section>
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
                <dd>{data.lineup_slot ?? "None"}</dd>
              </div>
              <div>
                <dt>Eligible slots</dt>
                <dd>{data.eligible_slots.join(", ") || "Unknown"}</dd>
              </div>
              <div>
                <dt>Injury</dt>
                <dd>
                  {data.injury_status || (data.injured ? "Injury reported" : "None reported")}
                </dd>
              </div>
              <div>
                <dt>Roster status</dt>
                <dd>{data.active ? "Active" : "Inactive"}</dd>
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
                    .join(", ") || "None"}
                </dd>
              </div>
            </dl>
            <p className="fine">
              <span className="state-off">Projections off</span>
              Evaluations appear here once player projections are built.
            </p>
            <p className="fine">
              <SourceNote snapshot={query.data.snapshot} />
            </p>
          </>
        )}
      </div>
    </dialog>
  );
}
