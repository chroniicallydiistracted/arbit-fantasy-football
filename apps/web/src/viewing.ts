import { useSyncExternalStore } from "react";

// The team the read-only dev account is looking at, chosen in Front Office and kept for this tab
// so Live shows that manager's players (R-039). Members never set it; their teams come from the
// server.
const KEY = "arbit.viewing-team";
const EVENT = "arbit-viewing-team";

export function viewingTeam(): string | null {
  return sessionStorage.getItem(KEY);
}

export function setViewingTeam(id: string | null) {
  if (id) sessionStorage.setItem(KEY, id);
  else sessionStorage.removeItem(KEY);
  window.dispatchEvent(new Event(EVENT));
}

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange);
  return () => window.removeEventListener(EVENT, onChange);
}

export function useViewingTeam(): string | null {
  return useSyncExternalStore(subscribe, viewingTeam, () => null);
}
