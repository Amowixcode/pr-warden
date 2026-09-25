import { useCallback, useEffect, useState } from "react";

export type Route =
  | { view: "home" }
  | { view: "section"; section: "history" | "prs" | "ingest"; jobId?: string }
  | { view: "review-form"; prefillRepo?: string; prefillPr?: number; jobId?: string }
  | { view: "review-detail"; id: number };

const HOME_ROUTE: Route = { view: "home" };

function currentHash(): string {
  return window.location.hash;
}

/**
 * Parse a `window.location.hash` value into a Route. Pure and DOM-free so it's directly
 * unit-testable. Anything unrecognized falls back to home — the landing page must never be a
 * dead route.
 */
export function parseHash(hash: string): Route {
  const raw = hash.startsWith("#") ? hash.slice(1) : hash;
  const [path, query] = raw.split("?");
  const segments = path
    .split("/")
    .map((s) => s.trim())
    .filter(Boolean);

  if (segments.length === 0 || segments[0] === "home") {
    return HOME_ROUTE;
  }

  if (segments[0] === "review") {
    if (segments[1] && /^\d+$/.test(segments[1])) {
      return { view: "review-detail", id: Number(segments[1]) };
    }
    const params = new URLSearchParams(query ?? "");
    const prefillRepo = params.get("repo") ?? undefined;
    const prRaw = params.get("pr");
    const prefillPr = prRaw && /^\d+$/.test(prRaw) ? Number(prRaw) : undefined;
    const jobId = params.get("job") ?? undefined;
    return { view: "review-form", prefillRepo, prefillPr, jobId };
  }

  if (segments[0] === "history" || segments[0] === "prs" || segments[0] === "ingest") {
    const params = new URLSearchParams(query ?? "");
    const jobId = params.get("job") ?? undefined;
    return { view: "section", section: segments[0], jobId };
  }

  return HOME_ROUTE;
}

export function useHashRoute(): { route: Route; navigate: (hash: string) => void } {
  const [route, setRoute] = useState<Route>(() => parseHash(currentHash()));

  useEffect(() => {
    function onHashChange() {
      setRoute(parseHash(currentHash()));
    }
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const navigate = useCallback((hash: string) => {
    const next = hash.startsWith("#") ? hash : `#${hash}`;
    if (window.location.hash === next) {
      // Setting the same hash doesn't fire hashchange — update state directly so
      // e.g. clicking "Review another PR" while already on #/review still resets the form.
      setRoute(parseHash(next));
      return;
    }
    window.location.hash = next;
  }, []);

  return { route, navigate };
}
