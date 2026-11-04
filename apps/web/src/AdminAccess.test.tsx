import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { AdminAccess } from "./AdminAccess";

const refresh = vi.fn();
const viewer = vi.hoisted(() => ({ observer: false }));
vi.mock("./session", () => ({
  useSession: () => ({
    auth: { csrf_token: "test-csrf" },
    me: { fixture: false, observer: viewer.observer, account: { id: "admin" } },
    refresh,
  }),
}));
afterEach(() => {
  vi.unstubAllGlobals();
  viewer.observer = false;
});
it("creates a private invitation only on explicit submission and keeps assignment approval separate", async () => {
  const calls: { url: string; body?: string; csrf?: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, options: RequestInit) => {
      calls.push({
        url,
        body: options.body as string,
        csrf: (options.headers as Record<string, string>)["X-CSRF-Token"],
      });
      return new Response(
        JSON.stringify(
          url.endsWith("directory")
            ? {
                accounts: [
                  {
                    id: "member",
                    role: "member",
                    display_name: "Fictional member",
                    suspended: false,
                    manager_ids: [],
                  },
                ],
                managers: [
                  {
                    id: "manager",
                    display_name: "ESPNFAN001",
                    first_name: "Avery",
                    team_ids: [],
                    team_names: ["Juniper Club"],
                  },
                ],
              }
            : { invitation_url: "https://arbit.invalid/join#private-test-token" },
        ),
      );
    }),
  );
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <AdminAccess />
    </QueryClientProvider>,
  );
  await screen.findByRole("option", { name: "Fictional member" });
  expect(calls.every((call) => call.url.endsWith("directory"))).toBe(true);
  expect(screen.getByRole("option", { name: "Avery — Juniper Club" })).toBeVisible();
  fireEvent.change(screen.getByLabelText("Google account email"), {
    target: { value: "member@fiction.invalid" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create invitation" }));
  await screen.findByDisplayValue("https://arbit.invalid/join#private-test-token");
  expect(calls.find((call) => call.url.endsWith("invitations"))).toMatchObject({
    body: '{"email":"member@fiction.invalid","role":"member"}',
    csrf: "test-csrf",
  });
  expect(calls.some((call) => call.url.endsWith("bindings"))).toBe(false);
  fireEvent.change(screen.getByLabelText("Member account"), { target: { value: "member" } });
  fireEvent.change(screen.getByLabelText("FFA manager"), { target: { value: "manager" } });
  fireEvent.click(screen.getByRole("button", { name: "Assign team" }));
  await waitFor(() => expect(calls.some((call) => call.url.endsWith("bindings"))).toBe(true));
  expect(calls.find((call) => call.url.endsWith("bindings"))).toMatchObject({
    body: '{"account_id":"member","manager_id":"manager"}',
    csrf: "test-csrf",
  });
});

it("shows the read-only dev account league access without letting it change anything", async () => {
  viewer.observer = true;
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      return new Response(
        JSON.stringify({
          accounts: [
            {
              id: "member",
              role: "member",
              display_name: "Fictional member",
              suspended: false,
              manager_ids: ["manager"],
            },
          ],
          managers: [
            {
              id: "manager",
              display_name: "ESPNFAN001",
              first_name: "Avery",
              team_ids: [],
              team_names: ["Juniper Club"],
            },
          ],
        }),
      );
    }),
  );
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <AdminAccess />
    </QueryClientProvider>,
  );
  await screen.findByRole("option", { name: "Fictional member" });
  expect(screen.getByText(/The dev account is read-only/)).toBeVisible();
  fireEvent.change(screen.getByLabelText("Member account"), { target: { value: "member" } });
  fireEvent.change(screen.getByLabelText("FFA manager"), { target: { value: "manager" } });
  for (const name of [
    "Create invitation",
    "Assign team",
    "Remove team",
    "Revoke sessions",
    "Suspend member",
  ]) {
    expect(screen.getByRole("button", { name })).toBeDisabled();
  }
  expect(calls.every((url) => url.endsWith("directory"))).toBe(true);
});
