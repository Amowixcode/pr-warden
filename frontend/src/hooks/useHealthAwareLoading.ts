import { useCallback, useState } from "react";
import { getHealth } from "../api/client";

export type LoadingPhase = "idle" | "waking" | "running";

/**
 * Distinguishes "the Render free-tier instance hasn't answered /health yet" from "it's awake
 * and the real request is in flight" — the only two states knowable without a job/polling API.
 * Fires a parallel, best-effort /health check when a request starts; if it resolves while
 * still "waking", flips to "running". A slow or failed health check never blocks or regresses
 * an already-"running" phase.
 */
export function useHealthAwareLoading(): {
  phase: LoadingPhase;
  run: <T>(task: () => Promise<T>) => Promise<T>;
} {
  const [phase, setPhase] = useState<LoadingPhase>("idle");

  const run = useCallback(async <T>(task: () => Promise<T>): Promise<T> => {
    setPhase("waking");
    getHealth()
      .then(() => setPhase((p) => (p === "waking" ? "running" : p)))
      .catch(() => {
        // The liveness check itself failing doesn't change what we know — stay "waking"
        // until the real request settles.
      });
    try {
      return await task();
    } finally {
      setPhase("idle");
    }
  }, []);

  return { phase, run };
}
