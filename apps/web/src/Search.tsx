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
      <label htmlFor="player-search" className="sr-only">
        Search players
      </label>
      <input
        id="player-search"
        type="search"
        value={input}
        maxLength={80}
        placeholder="Search players"
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
      <span id="search-help" className="sr-only">
        Enter at least two letters. Tab to a result to open it.
      </span>
      {term.length >= 2 && (
        <section className="search-results" aria-label="Player search results">
          <div className="search-result-heading">
            <span>
              {query.isPending
                ? "Searching…"
                : query.isError
                  ? "Search unavailable"
                  : `${query.data?.players.length ?? 0} found`}
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
          {query.isError && <p role="alert">Search failed. Try again.</p>}
          {query.data?.players.length === 0 && <p>No players match that name.</p>}
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
            <p>First 20 shown. Type more of the name to narrow it.</p>
          )}
        </section>
      )}
    </div>
  );
}
