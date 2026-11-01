import "@fontsource/instrument-sans/latin-400.css";
import "@fontsource/instrument-sans/latin-500.css";
import "@fontsource/instrument-sans/latin-600.css";
import "@fontsource/newsreader/latin-400.css";
import "@fontsource/newsreader/latin-400-italic.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { App } from "./App";
import { SessionProvider } from "./session";
import "./styles.css";

// Invitation fragments never enter a request, query cache, browser storage or provider URL.
const invitation = window.location.pathname === "/join" ? window.location.hash.slice(1) : undefined;
if (window.location.hash)
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
const client = new QueryClient({
  defaultOptions: {
    queries: { retry: false, staleTime: 30_000, gcTime: 5 * 60_000 },
    mutations: { retry: false },
  },
});
const root = document.getElementById("root");
if (!root) throw new Error("Application root missing");
createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <SessionProvider>
          <App invitation={invitation} />
        </SessionProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
