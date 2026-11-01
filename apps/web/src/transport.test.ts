import { afterEach, describe, expect, it, vi } from "vitest";
import { http, SessionLostError } from "./transport";

afterEach(() => vi.unstubAllGlobals());
describe("private transport", () => {
  it("uses same-origin credentials and forbids browser caching and redirects", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response('{"ok":true}'));
    vi.stubGlobal("fetch", fetcher);
    await http("/api/v1/me", { method: "PUT", body: { theme: "dark" }, csrf: "test-csrf" });
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/me",
      expect.objectContaining({
        credentials: "same-origin",
        cache: "no-store",
        redirect: "error",
        body: '{"theme":"dark"}',
        headers: expect.objectContaining({
          "X-CSRF-Token": "test-csrf",
          "Content-Type": "application/json",
        }),
      }),
    );
  });
  it("turns expired access into a distinct signal without exposing server contents", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("private-provider-detail", { status: 401 })),
    );
    await expect(http("/api/v1/me")).rejects.toBeInstanceOf(SessionLostError);
  });
  it("refuses arbitrary external or unapproved paths before a request", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    await expect(http("https://example.org/auth")).rejects.toThrow();
    await expect(http("/internal/league/current")).rejects.toThrow();
    await expect(http("//example.org/auth/")).rejects.toThrow();
    await expect(http("/api/v1/../../internal/league/current")).rejects.toThrow();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("makes preference conflicts recoverable without silently overwriting another tab", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 409 })));
    await expect(http("/api/v1/me/preferences")).rejects.toMatchObject({ status: 409 });
  });
});

it.each(["Ja'Marr", "D'Andre"])("allows an apostrophe in a player search for %s", async (name) => {
  const fetcher = vi.fn().mockResolvedValue(new Response('{"players":[]}'));
  vi.stubGlobal("fetch", fetcher);
  await expect(http(`/api/v1/players?query=${encodeURIComponent(name)}&limit=20`)).resolves.toEqual(
    { players: [] },
  );
  expect(fetcher).toHaveBeenCalledTimes(1);
  const request = new URL(fetcher.mock.calls[0][0], window.location.origin);
  expect(request.searchParams.get("query")).toBe(name);
});
