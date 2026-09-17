import { useEffect, useState } from "react";
import { getJob } from "../api/client";
import type { Job, JobStatus } from "../api/types";

export interface JobPollingState {
  status: JobStatus | null;
  stage: string | null;
  result: Job["result"];
  error: string | null;
}

const DEFAULT_INTERVAL_MS = 2000;

function _idle(): JobPollingState {
  return { status: null, stage: null, result: null, error: null };
}

/**
 * Polls GET /jobs/{jobId} until the job reaches a terminal status, or stops when jobId is
 * cleared/changed/unmounted. Same setInterval + cleanup-on-unmount shape as useElapsedSeconds
 * — the one other repeating-timer hook in this codebase.
 */
export function useJobPolling(
  jobId: string | undefined,
  intervalMs: number = DEFAULT_INTERVAL_MS,
): JobPollingState {
  const [state, setState] = useState<JobPollingState>(_idle);

  useEffect(() => {
    if (!jobId) {
      setState(_idle());
      return;
    }

    let cancelled = false;
    const intervalRef: { current: ReturnType<typeof setInterval> | null } = { current: null };

    async function poll() {
      try {
        const job = await getJob(jobId as string);
        if (cancelled) return;
        setState({ status: job.status, stage: job.stage, result: job.result, error: job.error });
        if (job.status !== "running" && intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      } catch {
        // A transient network hiccup shouldn't stop polling — the next tick tries again.
      }
    }

    setState({ status: "running", stage: null, result: null, error: null });
    void poll();
    intervalRef.current = setInterval(poll, intervalMs);

    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [jobId, intervalMs]);

  return state;
}
