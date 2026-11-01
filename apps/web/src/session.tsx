import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  Fragment,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import type { AuthStatus, Me, Preferences } from "./api";
import type { components } from "./generated/api";
import { http } from "./transport";

type Session = {
  online: boolean;
  auth?: AuthStatus;
  me?: Me;
  loading: boolean;
  error: boolean;
  expired: boolean;
  refresh: () => Promise<void>;
  start: (invitation?: string) => Promise<void>;
  fixtureLogin: (member: "one" | "two") => Promise<void>;
  logout: () => Promise<void>;
  save: (preferences: Preferences) => Promise<void>;
};
const Context = createContext<Session | null>(null);
export function SessionProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const [online, setOnline] = useState(navigator.onLine);
  const [auth, setAuth] = useState<AuthStatus>();
  const [me, setMe] = useState<Me>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [expired, setExpired] = useState(false);
  const flow = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const fixture = useRef(false);
  const identity = useRef<{ account: string; csrf: string | null } | null>(null);
  const [privateEpoch, setPrivateEpoch] = useState(0);
  const clearPrivate = useCallback(() => {
    void client.cancelQueries();
    client.clear();
    identity.current = null;
    setMe(undefined);
    setAuth(undefined);
    setPrivateEpoch((value) => value + 1);
  }, [client]);
  const forget = useCallback(() => {
    generation.current++;
    flow.current?.abort();
    clearPrivate();
    setAuth({ enabled: true, authenticated: false, csrf_token: null, fixture: fixture.current });
  }, [clearPrivate]);
  const refresh = useCallback(async () => {
    flow.current?.abort();
    const controller = new AbortController();
    flow.current = controller;
    const epoch = ++generation.current;
    try {
      const status = await http<AuthStatus>("/auth/status", { signal: controller.signal });
      if (generation.current !== epoch) return;
      fixture.current = status.fixture;
      if (status.authenticated) {
        // Shared cookies can change in another tab. Never combine a new session
        // with the previous member's cached facts or private component state.
        if (identity.current && identity.current.csrf !== status.csrf_token) {
          clearPrivate();
          setLoading(true);
        }
        const member = await http<Me>("/api/v1/me", { signal: controller.signal });
        if (generation.current === epoch) {
          if (identity.current && identity.current.account !== member.account.id) clearPrivate();
          identity.current = { account: member.account.id, csrf: status.csrf_token };
          setMe(member);
          setAuth(status);
        }
      } else {
        clearPrivate();
        setAuth(status);
      }
      setError(false);
    } catch {
      if (!controller.signal.aborted && generation.current === epoch) {
        forget();
        setError(true);
        setLoading(false);
      }
    } finally {
      if (flow.current === controller && !controller.signal.aborted) setLoading(false);
    }
  }, [clearPrivate, forget]);
  useEffect(() => {
    if (navigator.onLine) void refresh();
    else setLoading(false);
    const offline = () => {
      setOnline(false);
      forget();
      setLoading(false);
    };
    const connected = () => {
      setOnline(true);
      setLoading(true);
      void refresh();
    };
    const ended = () => {
      forget();
      setExpired(true);
      setLoading(false);
    };
    const focus = () => {
      if (navigator.onLine) void refresh();
    };
    window.addEventListener("offline", offline);
    window.addEventListener("online", connected);
    window.addEventListener("arbit:session-ended", ended);
    window.addEventListener("focus", focus);
    return () => {
      flow.current?.abort();
      window.removeEventListener("offline", offline);
      window.removeEventListener("online", connected);
      window.removeEventListener("arbit:session-ended", ended);
      window.removeEventListener("focus", focus);
    };
  }, [forget, refresh]);
  useEffect(() => {
    document.documentElement.dataset.theme =
      online && auth?.authenticated ? (me?.preferences.theme ?? "system") : "system";
    return () => {
      document.documentElement.dataset.theme = "system";
    };
  }, [me?.preferences.theme, online, auth?.authenticated]);
  useEffect(() => {
    if (!online || !auth?.authenticated) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible" && navigator.onLine) void refresh();
    }, 60_000);
    return () => window.clearInterval(timer);
  }, [online, auth?.authenticated, refresh]);
  async function start(invitation?: string) {
    const result = await http<components["schemas"]["StartResponse"]>("/auth/start", {
      method: "POST",
      body: { invitation: invitation || null },
    });
    const target = new URL(result.authorization_url);
    if (
      target.protocol !== "https:" &&
      !(auth?.fixture && target.origin === window.location.origin)
    )
      throw new Error("Sign-in is unavailable. Contact the league administrator.");
    window.location.assign(target.href);
  }
  async function fixtureLogin(member: "one" | "two") {
    await http("/auth/fixture", { method: "POST", body: { member } });
    forget();
    setExpired(false);
    setLoading(true);
    await refresh();
  }
  async function logout() {
    await http("/auth/logout", { method: "POST", csrf: auth?.csrf_token });
    forget();
    setExpired(false);
  }
  async function save(preferences: Preferences) {
    const epoch = generation.current;
    try {
      const result = await http<Preferences>("/api/v1/me/preferences", {
        method: "PUT",
        body: preferences,
        csrf: auth?.csrf_token,
      });
      if (generation.current === epoch)
        setMe((current) => (current ? { ...current, preferences: result } : current));
    } catch (failure) {
      if (generation.current === epoch) await refresh();
      throw failure;
    }
  }
  return (
    <Context
      value={{
        online,
        auth,
        me,
        loading,
        error,
        expired,
        refresh,
        start,
        fixtureLogin,
        logout,
        save,
      }}
    >
      <Fragment key={privateEpoch}>{children}</Fragment>
    </Context>
  );
}
export function useSession(): Session {
  const value = useContext(Context);
  if (!value) throw new Error("Session provider is required");
  return value;
}
