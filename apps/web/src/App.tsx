import { useEffect, useState } from "react";
import { Link, Navigate, NavLink, Route, Routes, useLocation } from "react-router";
import { FrontOffice } from "./FrontOffice";
import { PlayerDrawer } from "./PlayerDrawer";
import { Arrow, Busy, Empty, Notice } from "./primitives";
import { PwaControls } from "./pwa";
import { PlayerSearchBox } from "./Search";
import { Settings, Watchlist } from "./Settings";
import { useSession } from "./session";

const modules = [
  { path: "/front-office", title: "Front Office", index: "01" },
  { path: "/draft", title: "Draft", index: "02" },
  { path: "/scout", title: "Scout", index: "03" },
  { path: "/market", title: "Market", index: "04" },
  { path: "/lineup", title: "Lineup", index: "05" },
  { path: "/live", title: "Live", index: "06" },
  { path: "/archive", title: "Archive", index: "07" },
];
export function App({ invitation }: { invitation?: string }) {
  const session = useSession();
  const location = useLocation();
  const [menu, setMenu] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    setMenu(false);
    setError("");
    document.title = `Arbit · ${modules.find((item) => item.path === location.pathname)?.title ?? "FFA Front Office"}`;
  }, [location.pathname]);
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape" && menu) {
        setMenu(false);
        document.getElementById("menu-toggle")?.focus();
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [menu]);
  async function logout() {
    try {
      await session.logout();
    } catch (value) {
      setError(
        value instanceof Error ? value.message : "Sign-out could not be confirmed. Try again.",
      );
    }
  }
  if (!session.online)
    return (
      <div className="access-wrap">
        <Brand />
        <Empty eyebrow="Connection paused" title="Reconnect to open your front office.">
          <p>
            You’re offline. Your private league details have been cleared from this view. They’ll
            load again over a secure connection.
          </p>
          <button type="button" className="primary" onClick={() => window.location.reload()}>
            Try again <Arrow />
          </button>
        </Empty>
      </div>
    );
  if (session.loading)
    return (
      <div className="access-wrap">
        <Brand />
        <Busy label="Checking your seat in the front office…" />
      </div>
    );
  if (!session.auth?.authenticated || session.error || !session.me)
    return <SignIn invitation={invitation} />;
  const me = session.me;
  const team = me.teams.find((value) => value.id === me.current_team_id);
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      {me.fixture && (
        <div className="fixture-banner">
          Fictional preview · Dedicated test league · No real FFA data or provider sign-in
        </div>
      )}
      <div className="app-shell">
        <aside
          id="league-navigation"
          className={`sidebar ${menu ? "is-open" : ""}`}
          aria-label="League navigation"
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setMenu(false);
              document.getElementById("menu-toggle")?.focus();
            }
          }}
        >
          <Brand />
          <p className="sidebar-label">Your front office</p>
          <nav className="main-nav" aria-label="Workspaces">
            {modules.map((item) => (
              <NavLink key={item.path} to={item.path}>
                <span className="nav-index">{item.index}</span>
                {item.title}
                {item.path === "/front-office" && (
                  <span className="nav-active-dot" aria-hidden="true" />
                )}
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <nav className="utility-nav" aria-label="Account">
              <NavLink to="/watchlist">
                Watchlist <span>{me.preferences.watchlist.length || ""}</span>
              </NavLink>
              <NavLink to="/settings">Preferences</NavLink>
            </nav>
            <div className="member-label">
              <span className="member-monogram" aria-hidden="true">
                {me.account.display_name.slice(0, 1)}
              </span>
              <span>
                <strong>{me.account.display_name}</strong>
                <small>{team?.name ?? "Assignment pending"}</small>
              </span>
            </div>
            <button className="sign-out" type="button" onClick={() => void logout()}>
              Sign out <Arrow />
            </button>
          </div>
        </aside>
        <div className="app-body">
          <header className="topbar">
            <button
              id="menu-toggle"
              aria-controls="league-navigation"
              className="menu-toggle"
              type="button"
              aria-label="Toggle navigation"
              aria-expanded={menu}
              onClick={() => setMenu(!menu)}
            >
              {menu ? "Close" : "Menu"}
            </button>
            <div className="league-identity">
              <strong>FFA</strong>
              <span>{me.season} season</span>
            </div>
            {me.binding_status === "bound" && <PlayerSearchBox />}
          </header>
          <main id="main" tabIndex={-1} className="workspace">
            {error && <Notice danger>{error}</Notice>}
            {me.binding_status === "pending" && location.pathname !== "/settings" ? (
              <Empty eyebrow="Welcome to Arbit" title="Your seat is reserved.">
                <p>
                  You’re signed in. Your league administrator still needs to connect your account to
                  your FFA team.
                </p>
                <p>You won’t need to choose or claim a team yourself.</p>
                <button type="button" className="primary" onClick={() => void session.refresh()}>
                  Check assignment <Arrow />
                </button>
              </Empty>
            ) : (
              <Routes>
                <Route path="/front-office" element={<FrontOffice />} />
                <Route path="/watchlist" element={<Watchlist />} />
                <Route path="/settings" element={<Settings />} />
                <Route
                  path="/model"
                  element={
                    <Coming
                      title="Player analysis"
                      text="Shared player evaluations and recommendations will follow once the model has been built and verified. Front Office currently presents saved official league facts."
                    />
                  }
                />
                {modules
                  .filter((item) => item.path !== "/front-office")
                  .map((item) => (
                    <Route
                      key={item.path}
                      path={item.path}
                      element={<Coming title={item.title} text={futureCopy[item.path]} />}
                    />
                  ))}
                <Route path="/" element={<Navigate to="/front-office" replace />} />
                <Route path="/join" element={<Navigate to="/front-office" replace />} />
                <Route path="/login" element={<Navigate to="/front-office" replace />} />
                <Route
                  path="*"
                  element={
                    <Empty eyebrow="Page unavailable" title="Let’s get you back to the league.">
                      <p>This page could not be found.</p>
                      <Link to="/front-office" className="primary">
                        Open Front Office <Arrow />
                      </Link>
                    </Empty>
                  }
                />
              </Routes>
            )}
          </main>
          <footer className="workspace-footer">
            <span>ARBIT / FFA</span>
            <span>Your league. In perspective.</span>
          </footer>
        </div>
      </div>
      {me.binding_status === "bound" && <PlayerDrawer />}
      <PwaControls />
    </>
  );
}
function Brand() {
  return (
    <Link className="brand" to="/front-office" aria-label="Arbit Front Office">
      <img src="/mark.svg" alt="" width="36" height="36" />
      <span>
        Arbit<span className="brand-period">.</span>
        <small>FFA FANTASY FOOTBALL</small>
      </span>
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
      setError(value instanceof Error ? value.message : "Sign-in could not be started. Try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="sign-in">
      <div className="sign-in-story">
        <Brand />
        <div className="sign-in-headline">
          <p className="eyebrow">Built for the FFA</p>
          <h1>
            A seat in
            <br />
            the <em>front office.</em>
          </h1>
          <p>
            Your roster, your matchup, your league.
            <br />A considered view of the season.
          </p>
        </div>
        <div className="sign-in-foot">
          <span>ARBIT</span>
          <span>FFA · 2026</span>
        </div>
      </div>
      <div className="sign-in-form">
        <div className="sign-in-content">
          <p className="eyebrow">Members only</p>
          <h2>{invitation ? "You’re invited." : "Welcome back."}</h2>
          <p>
            Sign in with your invited account. Your FFA team is connected by your league
            administrator.
          </p>
          {session.expired && <Notice>Your session has ended. Sign in again to continue.</Notice>}
          {session.error && (
            <Notice danger>
              Member access could not be reached. Try again or contact your league administrator.
            </Notice>
          )}
          {session.error && (
            <button type="button" onClick={() => void session.refresh()}>
              Try member access again
            </button>
          )}
          {signInFailed && (
            <Notice danger>
              Sign-in could not be completed. Use the account named in your invitation, or request a
              new invitation.
            </Notice>
          )}
          {error && <Notice danger>{error}</Notice>}
          {session.auth?.fixture ? (
            <div className="fixture-login">
              <p>
                <strong>Fictional preview</strong>
                <br />
                These accounts use a separate test league. This does not test real provider sign-in.
              </p>
              <button
                className="primary"
                type="button"
                disabled={busy}
                onClick={() => void start("one")}
              >
                Open preview · Member one <Arrow />
              </button>
              <button type="button" disabled={busy} onClick={() => void start("two")}>
                Open preview · Member two <Arrow />
              </button>
            </div>
          ) : (
            <button
              className="primary"
              type="button"
              disabled={busy || !session.auth?.enabled || session.error}
              onClick={() => void start()}
            >
              {busy ? "Opening sign-in…" : "Continue to sign in"}
              <Arrow />
            </button>
          )}
          <p className="sign-in-help">
            Need an invitation or a team assignment?
            <br />
            Contact your FFA league administrator.
          </p>
        </div>
        <span className="access-note">Private access · Read-only league connection</span>
      </div>
      <PwaControls />
    </main>
  );
}
const futureCopy: Record<string, string> = {
  "/draft":
    "Draft preparation and pick decisions will be built around verified player evaluations and the FFA’s actual draft rules.",
  "/scout":
    "Player research, game logs and comparisons are planned here. You can already find a player and inspect their saved official facts using search.",
  "/market":
    "Trade and waiver analysis will follow the shared player model and verified FFA transaction rules.",
  "/lineup":
    "Start and sit decisions will follow verified player evaluations. Your saved roster and reported lineup locks are in Front Office.",
  "/live":
    "The live game workspace is still ahead. Verified play coverage and clear score distinctions will come before the full experience.",
  "/archive":
    "League history and season review are planned here. Saved matchup totals are available through Front Office’s matchup selector.",
};
function Coming({ title, text }: { title: string; text: string }) {
  return (
    <Empty eyebrow="A workspace to come" title={title}>
      <p>{text}</p>
      <Link to="/front-office" className="text-link">
        Return to Front Office <Arrow />
      </Link>
    </Empty>
  );
}
