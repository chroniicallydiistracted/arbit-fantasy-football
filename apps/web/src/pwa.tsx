import { useEffect, useRef, useState } from "react";

type InstallPrompt = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: string }>;
};
export function PwaControls() {
  const [waiting, setWaiting] = useState<ServiceWorker | null>(null);
  const [install, setInstall] = useState<InstallPrompt | null>(null);
  const applying = useRef(false);
  useEffect(() => {
    const offerInstall = (event: Event) => {
      event.preventDefault();
      setInstall(event as InstallPrompt);
    };
    const installed = () => setInstall(null);
    window.addEventListener("beforeinstallprompt", offerInstall);
    window.addEventListener("appinstalled", installed);
    let stopped = false;
    let registration: ServiceWorkerRegistration | undefined;
    const controller = () => {
      if (applying.current) window.location.reload();
    };
    if ("serviceWorker" in navigator && import.meta.env.PROD) {
      navigator.serviceWorker.addEventListener("controllerchange", controller);
      void navigator.serviceWorker
        .register("/sw.js", { scope: "/", updateViaCache: "none" })
        .then((value) => {
          registration = value;
          if (stopped) return;
          if (value.waiting) setWaiting(value.waiting);
          value.addEventListener("updatefound", () => {
            const incoming = value.installing;
            incoming?.addEventListener("statechange", () => {
              if (!stopped && incoming.state === "installed" && navigator.serviceWorker.controller)
                setWaiting(incoming);
            });
          });
        })
        .catch(() => {
          /* Online private application remains usable if static installation fails. */
        });
    }
    const check = () => {
      if (document.visibilityState === "visible") void registration?.update();
    };
    document.addEventListener("visibilitychange", check);
    return () => {
      stopped = true;
      window.removeEventListener("beforeinstallprompt", offerInstall);
      window.removeEventListener("appinstalled", installed);
      navigator.serviceWorker?.removeEventListener("controllerchange", controller);
      document.removeEventListener("visibilitychange", check);
    };
  }, []);
  if (!waiting && !install) return null;
  return (
    <aside className="pwa-offer" aria-label="Application options">
      {waiting && (
        <>
          <span>A new Arbit version is ready.</span>
          <button
            type="button"
            onClick={() => {
              applying.current = true;
              waiting.postMessage("APPLY_UPDATE");
            }}
          >
            Update & reload
          </button>
        </>
      )}
      {install && (
        <button
          type="button"
          onClick={async () => {
            await install.prompt();
            await install.userChoice;
            setInstall(null);
          }}
        >
          Install Arbit
        </button>
      )}
    </aside>
  );
}
