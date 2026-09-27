import { useState } from "react";
import { ApiError, NetworkError, reviewPr } from "../api/client";
import type { ReviewResponse } from "../api/types";
import { useHealthAwareLoading } from "../hooks/useHealthAwareLoading";
import { useJobPolling } from "../hooks/useJobPolling";
import { parseOwnerRepo } from "../lib/repoFormat";
import { ErrorBox } from "./ErrorBox";
import { JobStageBanner } from "./JobStageBanner";
import { LoadingBanner } from "./LoadingBanner";
import { ReviewResults } from "./ReviewResults";

export function ReviewForm({
  prefillRepo,
  prefillPr,
  jobId,
  onNavigate,
}: {
  prefillRepo?: string;
  prefillPr?: number;
  jobId?: string;
  onNavigate: (hash: string) => void;
}) {
  const [repo, setRepo] = useState(prefillRepo ?? "");
  const [prNumber, setPrNumber] = useState(prefillPr !== undefined ? String(prefillPr) : "");
  const { phase, run } = useHealthAwareLoading();
  const submitting = phase !== "idle";
  const [error, setError] = useState<string | null>(null);
  const job = useJobPolling(jobId);

  async function startJob(targetRepo: string, targetPr: number, full: boolean) {
    setError(null);
    const newJobId = crypto.randomUUID();
    try {
      await run(() => reviewPr(targetRepo, targetPr, newJobId, full));
      onNavigate(
        `#/review?repo=${encodeURIComponent(targetRepo)}&pr=${targetPr}&job=${newJobId}`,
      );
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof NetworkError
          ? err.message
          : "Something went wrong. Try again.",
      );
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!parseOwnerRepo(repo)) {
      setError("Expected 'owner/repo'.");
      return;
    }
    void startJob(repo, Number(prNumber), false);
  }

  function handleRerun() {
    if (!prefillRepo || !job.result) return;
    void startJob(prefillRepo, (job.result as ReviewResponse).pr_number, true);
  }

  return (
    <div>
      <form className="card" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="repo-input">Repository</label>
          <input
            id="repo-input"
            className="mono"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            placeholder="e.g. facebook/react or vercel/next.js"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="pr-number-input">PR number</label>
          <input
            id="pr-number-input"
            className="mono"
            type="number"
            min={1}
            value={prNumber}
            onChange={(e) => setPrNumber(e.target.value)}
            placeholder="123"
            required
          />
        </div>
        <button className="btn" type="submit" disabled={submitting}>
          {submitting ? "Starting…" : "Review PR"}
        </button>
      </form>

      <LoadingBanner phase={phase} runningLabel="Starting the review" />

      {error && <ErrorBox title="Couldn't start the review" message={error} />}

      {jobId && job.status === "running" && <JobStageBanner stage={job.stage} />}

      {jobId && job.status === "failed" && (
        <ErrorBox title="Review failed" message={job.error ?? "The review failed."} />
      )}

      {jobId && job.status === "succeeded" && job.result && prefillRepo && (
        <ReviewResults
          result={job.result as ReviewResponse}
          repo={prefillRepo}
          onRerun={handleRerun}
        />
      )}
    </div>
  );
}
