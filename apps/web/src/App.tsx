import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, Navigate, NavLink, Route, Routes, useLocation } from "react-router";
import type { FrontOffice as Office } from "./api";
import { LiveEvents, useFallbackInterval, useStreamState } from "./events";
import { FrontOffice } from "./FrontOffice";
import { points } from "./format";
import { LiveBoard } from "./Live";
import { PlayerDrawer } from "./PlayerDrawer";
import { Busy, Notice, PageTitle, SourceNote, StatePanel } from "./primitives";
import { PwaControls } from "./pwa";
import { PlayerSearchBox } from "./Search";
import { Settings, Watchlist } from "./Settings";
import { useSession } from "./session";
import { http } from "./transport";

const workspaces = [
  { path: "/front-office", title: "Front Office" },
  { path: "/draft", title: "Draft" },
  { path: "/scout", title: "Scout" },
  { path: "/market", title: "Market" },
  { path: "/lineup", title: "Lineup" },
  { path: "/live", title: "Live" },
  { path: "/archive", title: "Archive" },
];
// The five direct actions the design system allows on a phone; the rest live under More.
const phoneTabs = ["/front-office", "/lineup", "/scout", "/live"];

export function App({ invitation }: { invitation?: string }) {
  const session = useSession();
  const location = useLocation();
  const [more, setMore] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    setMore(false);
    setError("");
    const page = workspaces.find((item) => item.path === location.pathname);
    document.title = page ? `${page.title} · Arbit` : "Arbit";
  }, [location.pathname]);
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape" && more) {
        setMore(false);
        document.getElementById("more-toggle")?.focus();
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [more]);
  async function logout() {
    try {
      await session.logout();
    } catch (value) {
      setError(value instanceof Error ? value.message : "Sign-out failed. Try again.");
    }
  }
  if (!session.online)
    return (
      <div className="gate">
        <div className="gate-stripes" aria-hidden="true" />
        <main className="gate-panel">
          <h1 className="gate-title">Offline</h1>
          <p className="gate-sub">
            League data has been cleared from this view. It loads again when the connection returns.
          </p>
          <div className="first-down" />
          <div className="gate-actions">
            <button type="button" className="primary" onClick={() => window.location.reload()}>
              Retry
            </button>
          </div>
        </main>
      </div>
    );
  if (session.loading)
    return (
      <div className="page">
        <Busy label="Checking session…" />
      </div>
    );
  if (!session.auth?.authenticated || session.error || !session.me)
    return <SignIn invitation={invitation} />;
  const me = session.me;
  const team = me.teams.find((value) => value.id === me.current_team_id);
  const bound = me.binding_status === "bound";
  const memberLinks = (
    <>
      <NavLink to="/watchlist">
        Watchlist
        {me.preferences.watchlist.length > 0 && (
          <span className="count"> {me.preferences.watchlist.length}</span>
        )}
      </NavLink>
      <NavLink to="/settings">Preferences</NavLink>
    </>
  );
  const shell = (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      {me.fixture && (
        <div className="fixture-banner">Test data. Fictional league, no real FFA data.</div>
      )}
      {me.observer && (
        <div className="fixture-banner">
          Dev account, read-only. It can open every team and the administrator pages, and can’t
          change anything.
        </div>
      )}
      <div className="stripe-edge" aria-hidden="true" />
      <header className="band">
        <Brand />
        <nav className="tabs" aria-label="Workspaces">
          {workspaces.map((item) => (
            <NavLink key={item.path} className="tab" to={item.path}>
              {item.title}
            </NavLink>
          ))}
        </nav>
        <div className="band-tools">
          {bound && <PlayerSearchBox />}
          <div className="band-links">
            {memberLinks}
            <span className="member-label">
              <strong>{me.account.display_name}</strong>
              <span className="sr-only">{team?.name ?? "Team not assigned"}</span>
            </span>
            <button type="button" onClick={() => void logout()}>
              Sign out
            </button>
          </div>
        </div>
      </header>
      {bound && <ContextStrip season={me.season} teamId={me.current_team_id} />}
      <main id="main" tabIndex={-1} className="page">
        {error && <Notice danger>{error}</Notice>}
        {me.binding_status === "pending" && location.pathname !== "/settings" ? (
          <StatePanel title="Team not assigned">
            <p>
              You’re signed in. The league administrator has to assign your ESPN team before league
              data can load.
            </p>
            <div className="actions">
              <button type="button" className="primary" onClick={() => void session.refresh()}>
                Check again
              </button>
            </div>
          </StatePanel>
        ) : (
          <Routes>
            <Route path="/front-office" element={<FrontOffice />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/settings" element={<Settings />} />
            <Route
              path="/model"
              element={
                <Unbuilt
                  title="Recommendations"
                  text="Recommendations are off. Lineup, waiver and trade calls need player projections, which aren’t built yet."
                />
              }
            />
            <Route path="/live" element={<LiveBoard />} />
            <Route path="/live/games/:eventId" element={<LiveBoard />} />
            {workspaces
              .filter((item) => !["/front-office", "/live"].includes(item.path))
              .map((item) => (
                <Route
                  key={item.path}
                  path={item.path}
                  element={<Unbuilt title={item.title} text={unbuilt[item.path]} />}
                />
              ))}
            <Route path="/" element={<Navigate to="/front-office" replace />} />
            <Route path="/join" element={<Navigate to="/front-office" replace />} />
            <Route path="/login" element={<Navigate to="/front-office" replace />} />
            <Route
              path="*"
              element={
                <StatePanel title="Page not found">
                  <div className="actions">
                    <Link to="/front-office" className="link-button primary">
                      Front Office
                    </Link>
                  </div>
                </StatePanel>
              }
            />
          </Routes>
        )}
      </main>
      <nav className="bottom-tabs" aria-label="Workspaces, phone">
        {phoneTabs.map((path) => (
          <NavLink key={path} className="tab" to={path}>
            {workspaces.find((item) => item.path === path)?.title}
          </NavLink>
        ))}
        <button
          id="more-toggle"
          type="button"
          aria-controls="more-sheet"
          aria-expanded={more}
          onClick={() => setMore(!more)}
        >
          More
        </button>
      </nav>
      {more && (
        <nav id="more-sheet" className="more-sheet" aria-label="More">
          {workspaces
            .filter((item) => !phoneTabs.includes(item.path))
            .map((item) => (
              <NavLink key={item.path} to={item.path}>
                {item.title}
              </NavLink>
            ))}
          {memberLinks}
          <p>
            {me.account.display_name} · {team?.name ?? "Team not assigned"}
          </p>
          <button type="button" onClick={() => void logout()}>
            Sign out
          </button>
        </nav>
      )}
      {bound && <PlayerDrawer />}
      <PwaControls />
    </>
  );
  return bound ? <LiveEvents>{shell}</LiveEvents> : shell;
}

/** League context on every workspace: period, the member's current score, data age. */
function ContextStrip({ season, teamId }: { season: number; teamId?: string | null }) {
  const location = useLocation();
  const search = teamId ? `?team_id=${encodeURIComponent(teamId)}` : "";
  const stream = useStreamState();
  const interval = useFallbackInterval();
  const query = useQuery({
    queryKey: ["front-office", teamId, null],
    queryFn: ({ signal }) => http<Office>(`/api/v1/front-office?${search.slice(1)}`, { signal }),
    refetchInterval: interval,
  });
  const data = query.data;
  const own = data?.matchup
    ? data.matchup.home?.team_id === data.team.id
      ? data.matchup.home
      : data.matchup.away
    : null;
  const other = data?.matchup
    ? data.matchup.home?.team_id === data.team.id
      ? data.matchup.away
      : data.matchup.home
    : null;
  const opponent = data?.standings.find((team) => team.id === other?.team_id);
  return (
    <div className="context-strip">
      <span>
        <strong>FFA {season}</strong>
      </span>
      {data && <span>Matchup {data.snapshot.matchup_period}</span>}
      {data && location.pathname !== "/front-office" && own && (
        <Link className="scorebug" to="/front-office">
          <span>{data.team.abbreviation}</span>
          <b>{points(own.official_points)}</b>
          <b>{points(other?.official_points)}</b>
          <span>{opponent?.abbreviation ?? "—"}</span>
        </Link>
      )}
      <span className="context-push">
        {stream === "down" && (
          <span className="status" data-state="behind">
            Updates paused{" "}
          </span>
        )}
        {stream === "connecting" && (
          <span className="status" data-state="behind">
            Reconnecting{" "}
          </span>
        )}
        {data ? <SourceNote snapshot={data.snapshot} failed={query.isError} /> : null}
      </span>
    </div>
  );
}

function Brand() {
  return (
    <Link className="band-brand" to="/front-office" aria-label="Arbit, go to Front Office">
      <img src="/mark.svg" alt="" width="28" height="28" />
      <span>Arbit</span>
    </Link>
  );
}

function SignIn({ invitation }: { invitation?: string }) {
  const session = useSession();
  const signInFailed = new URLSearchParams(window.location.search).has("auth_error");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function start(member?: "one" | "two") {
    setBusy(true);
    setError("");
    try {
      if (member) await session.fixtureLogin(member);
      else await session.start(invitation);
    } catch (value) {
      setError(value instanceof Error ? value.message : "Sign-in failed to start. Try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="gate">
      <div className="gate-stripes" aria-hidden="true" />
      <main className="gate-panel">
        <h1 className="gate-title display">Arbit</h1>
        <p className="gate-sub">
          FFA Fantasy Football Companion
          <small>Family Football Association · 2026 season</small>
        </p>
        <div className="first-down" />
        {session.expired && <Notice>Your session ended. Sign in to continue.</Notice>}
        {session.error && (
          <Notice danger>
            Couldn’t reach Arbit. Try again, or contact the league administrator.
          </Notice>
        )}
        {signInFailed && (
          <Notice danger>
            Sign-in failed. Use the Google account your invitation was sent to, or ask for a new
            invitation.
          </Notice>
        )}
        {error && <Notice danger>{error}</Notice>}
        {session.auth?.fixture ? (
          <div className="gate-actions">
            <p className="fine">Test data. Fictional league, no real FFA data or Google sign-in.</p>
            <button
              className="primary"
              type="button"
              disabled={busy}
              onClick={() => void start("one")}
            >
              Sign in as test member one
            </button>
            <button type="button" disabled={busy} onClick={() => void start("two")}>
              Sign in as test member two
            </button>
          </div>
        ) : (
          <div className="gate-actions">
            {session.error ? (
              <button type="button" className="primary" onClick={() => void session.refresh()}>
                Retry
              </button>
            ) : (
              <button
                className="primary"
                type="button"
                disabled={busy || !session.auth?.enabled}
                onClick={() => void start()}
              >
                {busy
                  ? "Opening Google…"
                  : invitation
                    ? "Accept invitation"
                    : "Sign in with Google"}
              </button>
            )}
          </div>
        )}
        <p className="fine">
          {invitation
            ? "Use the Google account this invitation was sent to."
            : "Access is by invitation from the league administrator."}
        </p>
      </main>
      <PwaControls />
    </div>
  );
}

const unbuilt: Record<string, string> = {
  "/draft":
    "Not built yet. It needs player projections and full-draft simulation. The 2026 draft is complete, so its first live use is next season’s redraft.",
  "/scout":
    "Not built yet. Game logs, advanced metrics and comparisons need the stat pipeline. Search above opens a player’s current ESPN facts.",
  "/market":
    "Not built yet. Waiver and trade calls need player projections. The trade deadline and waiver rules are already stored.",
  "/lineup":
    "Not built yet. Sit and start calls need player projections. Your roster and lock status are on Front Office.",
  "/live":
    "Not built yet. Scores, play-by-play and field graphics are next in the live workstream.",
  "/archive":
    "Not built yet. This season’s matchup results are on Front Office. The first Geller Cup entry is decided when this season ends.",
};

function Unbuilt({ title, text }: { title: string; text: string }) {
  return (
    <>
      <PageTitle title={title} />
      <section className="state-panel">
        <p>{text}</p>
        <div className="actions">
          <Link to="/front-office" className="link-button">
            Front Office
          </Link>
        </div>
      </section>
    </>
  );
}
