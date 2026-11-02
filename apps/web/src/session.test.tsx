import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import type { Me } from "./api";
import { SessionProvider, useSession } from "./session";

const member: Me = {
  account: { id: "one", role: "member", display_name: "Fictional member one" },
  binding_status: "pending",
  current_team_id: null,
  team_id: null,
  season: 2026,
  teams: [],
  fixture: true,
  preferences: { version: 0, theme: "dark", watchlist: [] },
};
function Probe() {
  const value = useSession();
  return (
    <>
      <p>{value.loading ? "Checking" : (value.me?.account.display_name ?? "Signed out")}</p>
      <button type="button" onClick={() => void value.fixtureLogin("one")}>
        Preview sign-in
      </button>
      <button type="button" onClick={() => void value.logout()}>
        Sign out
      </button>
    </>
  );
}
function Starter({ onFailure }: { onFailure: (failure: Error) => void }) {
  const session = useSession();
  if (session.loading) return null;
  return (
    <button type="button" onClick={() => void session.start().catch(onFailure)}>
      Start sign-in
    </button>
  );
}
afterEach(() => {
  vi.unstubAllGlobals();
  document.documentElement.dataset.theme = "system";
});
it("signs in after an empty session and clears all member queries on logout", async () => {
  let signed = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url === "/auth/fixture") signed = true;
      if (url === "/auth/logout") signed = false;
      return new Response(
        JSON.stringify(
          url === "/auth/status"
            ? {
                enabled: true,
                authenticated: signed,
                csrf_token: signed ? "csrf" : null,
                fixture: true,
              }
            : url === "/api/v1/me"
              ? member
              : { success: true },
        ),
      );
    }),
  );
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <SessionProvider>
        <Probe />
      </SessionProvider>
    </QueryClientProvider>,
  );
  await screen.findByText("Signed out");
  fireEvent.click(screen.getByText("Preview sign-in"));
  await screen.findByText("Fictional member one");
  client.setQueryData(["front-office"], { private: "team facts" });
  fireEvent.click(screen.getByText("Sign out"));
  await screen.findByText("Signed out");
  expect(client.getQueryCache().getAll()).toHaveLength(0);
  expect(document.documentElement.dataset.theme).toBe("system");
});
it("blames the address, not the account, when the server refuses to start a sign-in", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      url === "/auth/start"
        ? new Response(JSON.stringify({ code: "ORIGIN_REQUIRED" }), { status: 403 })
        : new Response(
            JSON.stringify({
              enabled: true,
              authenticated: false,
              csrf_token: null,
              fixture: false,
            }),
          ),
    ),
  );
  let failure: Error | undefined;
  render(
    <QueryClientProvider client={new QueryClient()}>
      <SessionProvider>
        <Starter
          onFailure={(value) => {
            failure = value;
          }}
        />
      </SessionProvider>
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByText("Start sign-in"));
  await waitFor(() => expect(failure).toBeDefined());
  expect(failure?.message).toContain("address");
  expect(failure?.message).not.toMatch(/account/i);
});
it("clears member facts and their theme as soon as the device goes offline", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (url: string) =>
        new Response(
          JSON.stringify(
            url === "/auth/status"
              ? { enabled: true, authenticated: true, csrf_token: "csrf", fixture: true }
              : member,
          ),
        ),
    ),
  );
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <SessionProvider>
        <Probe />
      </SessionProvider>
    </QueryClientProvider>,
  );
  await screen.findByText("Fictional member one");
  client.setQueryData(["player", "private"], { display_name: "Private player" });
  fireEvent(window, new Event("offline"));
  await waitFor(() => expect(screen.getByText("Signed out")).toBeVisible());
  expect(client.getQueryCache().getAll()).toHaveLength(0);
  expect(document.documentElement.dataset.theme).toBe("system");
});
it("clears private facts on a server expiry/revocation signal", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (url: string) =>
        new Response(
          JSON.stringify(
            url === "/auth/status"
              ? { enabled: true, authenticated: true, csrf_token: "csrf", fixture: true }
              : member,
          ),
        ),
    ),
  );
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <SessionProvider>
        <Probe />
      </SessionProvider>
    </QueryClientProvider>,
  );
  await screen.findByText("Fictional member one");
  client.setQueryData(["front-office"], { private: "facts" });
  fireEvent(window, new Event("arbit:session-ended"));
  await screen.findByText("Signed out");
  expect(client.getQueryCache().getAll()).toHaveLength(0);
  expect(document.documentElement.dataset.theme).toBe("system");
});
function LocalPrivateNote() {
  const { me } = useSession();
  const [note] = useState(`Private note for ${me?.account.display_name}`);
  return <p>{note}</p>;
}
function ReplacementProbe() {
  const { me } = useSession();
  return me ? (
    <>
      <p>{me.account.display_name}</p>
      <LocalPrivateNote />
    </>
  ) : (
    <p>Checking account</p>
  );
}
it("clears old queries and local private state before replacing an account on focus", async () => {
  let current = member;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (url: string) =>
        new Response(
          JSON.stringify(
            url === "/auth/status"
              ? { enabled: true, authenticated: true, csrf_token: "same-test-csrf", fixture: true }
              : current,
          ),
        ),
    ),
  );
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <SessionProvider>
        <ReplacementProbe />
      </SessionProvider>
    </QueryClientProvider>,
  );
  await screen.findByText("Private note for Fictional member one");
  client.setQueryData(["front-office", "old-team-deep-link"], { private: "Old account facts" });
  current = {
    ...member,
    account: { ...member.account, id: "two", display_name: "Fictional member two" },
  };
  fireEvent(window, new Event("focus"));
  await screen.findByText("Fictional member two");
  expect(client.getQueryCache().getAll()).toHaveLength(0);
  expect(screen.queryByText("Private note for Fictional member one")).not.toBeInTheDocument();
  expect(screen.getByText("Private note for Fictional member two")).toBeVisible();
});
