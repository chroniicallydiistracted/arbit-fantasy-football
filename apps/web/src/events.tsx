import { useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext, useEffect, useRef, useState } from "react";
import { useSession } from "./session";

export type StreamState = "connecting" | "open" | "down";
const Context = createContext<StreamState>("connecting");
export const useStreamState = () => useContext(Context);

/** While the stream is healthy, queries wait for events. Otherwise they poll. */
export function useFallbackInterval(): number | false {
  return useStreamState() === "open" ? false : 30_000;
}

// Which cached reads each server event makes out of date.
const AFFECTS: Record<string, string[]> = {
  "league.updated": ["front-office", "player", "search", "sources"],
  "source.status": ["sources", "front-office"],
  "games.updated": ["live-games", "live-game", "live-plays", "sources"],
  "game.plays": ["live-plays", "live-animation", "sources"],
  "game.corrected": ["live-plays", "live-animation", "sources"],
  "game.summary": ["live-game"],
  "schedule.updated": ["front-office", "live-games"],
};

/**
 * One session-bound event stream per signed-in tab. Events say what changed; the affected
 * queries read it again through the normal authorized routes. EventSource reconnects by itself
 * and sends Last-Event-ID, so the server replays anything missed.
 */
export function LiveEvents({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const { refresh } = useSession();
  const [state, setState] = useState<StreamState>("connecting");
  const pending = useRef(new Set<string>());
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (typeof EventSource === "undefined") {
      setState("down");
      return;
    }
    const source = new EventSource("/api/v1/events");
    const flush = () => {
      timer.current = undefined;
      for (const key of pending.current) void client.invalidateQueries({ queryKey: [key] });
      pending.current.clear();
    };
    // Coalesce bursts: a busy NFL Sunday shouldn't cause a read per event.
    const schedule = (keys: string[]) => {
      for (const key of keys) pending.current.add(key);
      timer.current ??= window.setTimeout(flush, 250);
    };
    source.onopen = () => setState("open");
    source.onerror = () =>
      setState(source.readyState === EventSource.CLOSED ? "down" : "connecting");
    for (const [type, keys] of Object.entries(AFFECTS)) {
      source.addEventListener(type, () => schedule(keys));
    }
    source.addEventListener("snapshot.required", () => {
      void client.invalidateQueries();
    });
    source.addEventListener("session.ended", () => {
      source.close();
      setState("down");
      void refresh();
    });
    return () => {
      source.close();
      if (timer.current !== undefined) window.clearTimeout(timer.current);
      pending.current.clear();
    };
  }, [client, refresh]);
  return <Context value={state}>{children}</Context>;
}
