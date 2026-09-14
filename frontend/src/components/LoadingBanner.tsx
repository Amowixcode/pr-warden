import { useElapsedSeconds } from "../hooks/useElapsedSeconds";
import type { LoadingPhase } from "../hooks/useHealthAwareLoading";

/**
 * The only two knowable loading states without a job/polling API: the server hasn't answered
 * a liveness check yet, or it has and the real request is running. No stage indicator implying
 * per-agent progress — that would be as untrue as the string this replaces.
 */
export function LoadingBanner({
  phase,
  runningLabel = "Running",
}: {
  phase: LoadingPhase;
  /** What's running once the server is confirmed awake, e.g. "Running review". */
  runningLabel?: string;
}) {
  const elapsed = useElapsedSeconds(phase === "running");

  if (phase === "idle") {
    return null;
  }

  return (
    <div className="loading-banner">
      <span className="spinner" />
      {phase === "waking"
        ? "Waking up the server — this can take up to a minute on the first request."
        : `${runningLabel}… ${elapsed}s`}
    </div>
  );
}
