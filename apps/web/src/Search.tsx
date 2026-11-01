import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import type { PlayerSearch } from "./api";
import { http } from "./transport";
export function PlayerSearchBox() {
  const [input, setInput] = useState("");
  const [term, setTerm] = useState("");
  const [params, setParams] = useSearchParams();
  useEffect(() => {
    const timer = window.setTimeout(() => setTerm(input.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [input]);
  const query = useQuery({
    queryKey: ["search", term],
    queryFn: ({ signal }) =>
      http<PlayerSearch>(`/api/v1/players?query=${encodeURIComponent(term)}&limit=20`, { signal }),
    enabled: term.length >= 2,
  });
  return (
    <div className="player-search">
      <label htmlFor="player-search">Find a player</label>
      <div className="search-input">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none">
          <circle cx="10.5" cy="10.5" r="6.5" stroke="currentColor" strokeWidth="1.5" />
          <path d="m16 16 5 5" stroke="currentColor" strokeWidth="1.5" />
        </svg>
        <input
          id="player-search"
          type="search"
          value={input}
          maxLength={80}
          placeholder="Search the league’s players"
          autoComplete="off"
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setInput("");
              setTerm("");
            }
          }}
          aria-describedby="search-help"
        />
      </div>
      <span id="search-help" className="sr-only">
        Enter at least two characters. Tab to a result to open player details.
      </span>
      {term.length >= 2 && (
        <section className="search-results" aria-label="Player search results">
          <div className="search-result-heading">
            <span>
              {query.isPending
                ? "Searching…"
                : query.isError
                  ? "Search unavailable"
                  : `${query.data?.players.length ?? 0} results`}
            </span>
            <button
              type="button"
              onClick={() => {
                setInput("");
                setTerm("");
                document.getElementById("player-search")?.focus();
              }}
            >
              Close
            </button>
          </div>
          {query.isError && <p role="alert">Please try your search again shortly.</p>}
          {query.data?.players.length === 0 && (
            <p>No players match that name. Try a different spelling.</p>
          )}
          <ul>
            {query.data?.players.map((player) => (
              <li key={player.id}>
                <button
                  type="button"
                  onClick={() => {
                    const next = new URLSearchParams(params);
                    next.set("player", player.id);
                    next.set("player_snapshot", query.data.snapshot.id);
                    setParams(next);
                    setInput("");
                    setTerm("");
                  }}
                >
                  <span>{player.display_name}</span>
                  <span className="muted">{player.position}</span>
                </button>
              </li>
            ))}
          </ul>
          {query.data?.players.length === 20 && (
            <p>Showing the first 20. Refine your search for more specific results.</p>
          )}
        </section>
      )}
    </div>
  );
}
