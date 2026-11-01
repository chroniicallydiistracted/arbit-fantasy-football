import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { components } from "./generated/api";
import { Notice } from "./primitives";
import { useSession } from "./session";
import { http } from "./transport";

type Directory = components["schemas"]["AdminDirectory"];
type Manager = Directory["managers"][number];
function managerLabel(manager: Manager, all: Manager[]): string {
  const base = (value: Manager) =>
    [value.first_name?.trim() || value.display_name, ...(value.team_names ?? [])].join(" — ");
  const label = base(manager);
  return all.some((other) => other.id !== manager.id && base(other) === label)
    ? `${label} (${manager.display_name})`
    : label;
}

export function AdminAccess() {
  const { auth, me, refresh } = useSession();
  const query = useQuery({
    queryKey: ["admin-directory"],
    queryFn: ({ signal }) => http<Directory>("/api/v1/admin/directory", { signal }),
  });
  const [email, setEmail] = useState("");
  const [invite, setInvite] = useState("");
  const [account, setAccount] = useState("");
  const [manager, setManager] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(false);
  const selected = query.data?.accounts.find((value) => value.id === account);
  async function run(action: () => Promise<void>, success: string) {
    setBusy(true);
    setMessage("");
    setError(false);
    try {
      await action();
      setMessage(success);
      await query.refetch();
    } catch (failure) {
      setError(true);
      setMessage(
        failure instanceof Error ? failure.message : "The change wasn’t saved. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function createInvite() {
    const result = await http<components["schemas"]["InviteResponse"]>(
      "/api/v1/admin/invitations",
      { method: "POST", body: { email, role: "member" }, csrf: auth?.csrf_token },
    );
    setInvite(result.invitation_url);
    setEmail("");
  }
  async function bind(revoke = false) {
    await http(`/api/v1/admin/bindings${revoke ? "/revoke" : ""}`, {
      method: "POST",
      body: { account_id: account, manager_id: manager },
      csrf: auth?.csrf_token,
    });
    if (account === me?.account.id) await refresh();
  }
  async function revoke(suspend: boolean) {
    await http("/api/v1/admin/sessions/revoke", {
      method: "POST",
      body: { account_id: account, suspend },
      csrf: auth?.csrf_token,
    });
  }
  return (
    <section className="settings-section admin-access">
      <h2>League access</h2>
      <p>
        An invitation lets someone sign in. A team assignment is a separate approval. Changing an
        assignment signs that member out.
      </p>
      {me?.fixture && (
        <Notice>Test data. Invitations need Google sign-in and are disabled here.</Notice>
      )}
      {message && <Notice danger={error}>{message}</Notice>}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void run(createInvite, "Invitation created. Send the link to that member directly.");
        }}
      >
        <h3>Invite a member</h3>
        <label htmlFor="invitation-email">Google account email</label>
        <input
          id="invitation-email"
          type="email"
          maxLength={320}
          autoComplete="off"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <button type="submit" disabled={busy || me?.fixture}>
          Create invitation
        </button>
      </form>
      {invite && (
        <div className="private-invitation">
          <label htmlFor="private-invitation">Invitation link, expires in seven days</label>
          <input
            id="private-invitation"
            readOnly
            value={invite}
            onFocus={(event) => event.target.select()}
          />
          <button
            type="button"
            onClick={() =>
              void run(async () => {
                await navigator.clipboard.writeText(invite);
              }, "Invitation link copied.")
            }
          >
            Copy link
          </button>
          <button type="button" className="quiet" onClick={() => setInvite("")}>
            Hide link
          </button>
        </div>
      )}
      <div className="assignment-form">
        <h3>Assign a team</h3>
        {query.isError ? (
          <Notice
            danger
            action={
              <button type="button" onClick={() => void query.refetch()}>
                Retry
              </button>
            }
          >
            Members couldn’t be loaded.
          </Notice>
        ) : (
          <>
            <label htmlFor="assignment-account">Member account</label>
            <select
              id="assignment-account"
              value={account}
              onChange={(event) => {
                setAccount(event.target.value);
                setManager("");
              }}
            >
              <option value="">Choose a member</option>
              {query.data?.accounts.map((value) => (
                <option key={value.id} value={value.id}>
                  {value.display_name}
                  {value.suspended ? " · Suspended" : ""}
                  {value.id === me?.account.id ? " · You" : ""}
                </option>
              ))}
            </select>
            <label htmlFor="assignment-manager">FFA manager</label>
            <select
              id="assignment-manager"
              value={manager}
              onChange={(event) => setManager(event.target.value)}
            >
              <option value="">Choose a manager</option>
              {query.data?.managers.map((value) => (
                <option key={value.id} value={value.id}>
                  {managerLabel(value, query.data.managers)}
                </option>
              ))}
            </select>
            <p className="muted">
              Pick the ESPN manager this person actually is. Co-managers each have their own entry.
            </p>
            <div className="admin-actions">
              <button
                type="button"
                disabled={busy || !account || !manager || !!selected?.suspended}
                onClick={() =>
                  void run(() => bind(), "Team assigned. The member must sign in again.")
                }
              >
                Assign team
              </button>
              <button
                type="button"
                disabled={busy || !account || !manager || !selected?.manager_ids.includes(manager)}
                onClick={() =>
                  void run(() => bind(true), "Team removed. The member’s sessions were ended.")
                }
              >
                Remove team
              </button>
            </div>
            {selected && (
              <div className="session-actions">
                <h3>Member sessions</h3>
                {selected.suspended && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      void run(async () => {
                        await http("/api/v1/admin/accounts/reactivate", {
                          method: "POST",
                          body: { account_id: account },
                          csrf: auth?.csrf_token,
                        });
                      }, "Member reactivated. They must sign in again. Removed teams stay removed.")
                    }
                  >
                    Reactivate member
                  </button>
                )}
                <p className="muted">
                  Revoking ends every session for this member. Suspending also blocks future
                  sign-in.
                </p>
                <button
                  type="button"
                  disabled={busy || account === me?.account.id}
                  onClick={() => void run(() => revoke(false), "Sessions ended.")}
                >
                  Revoke sessions
                </button>
                {selected.role !== "admin" && !selected.suspended && (
                  <button
                    type="button"
                    disabled={busy || account === me?.account.id}
                    onClick={() => {
                      if (
                        window.confirm(`Suspend ${selected.display_name} and revoke their access?`)
                      )
                        void run(() => revoke(true), "Member suspended and sessions ended.");
                    }}
                  >
                    Suspend member
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
