import { useState } from "react";
import { ApiError, NetworkError, ingestRepository } from "../api/client";
import type { IngestResponse } from "../api/types";
import { useHealthAwareLoading } from "../hooks/useHealthAwareLoading";
import { useJobPolling } from "../hooks/useJobPolling";
import { parseOwnerRepo } from "../lib/repoFormat";
import { ErrorBox } from "./ErrorBox";
import { JobStageBanner } from "./JobStageBanner";
import { LoadingBanner } from "./LoadingBanner";

export function IngestForm({
  jobId,
  onNavigate,
}: {
  jobId?: string;
  onNavigate: (hash: string) => void;
}) {
  const [repo, setRepo] = useState("");
  const { phase, run } = useHealthAwareLoading();
  const submitting = phase !== "idle";
  const [error, setError] = useState<string | null>(null);
  const job = useJobPolling(jobId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!parseOwnerRepo(repo)) {
      setError("Expected 'owner/repo'.");
      return;
    }
    setError(null);
    const newJobId = crypto.randomUUID();
    try {
      await run(() => ingestRepository(repo, newJobId));
      onNavigate(`#/ingest?job=${newJobId}`);
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof NetworkError
          ? err.message
          : "Something went wrong. Try again.",
      );
    }
  }

  const result = job.result as IngestResponse | null;

  return (
    <div>
      <form className="card" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="ingest-repo-input">Repository</label>
          <input
            id="ingest-repo-input"
            className="mono"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            placeholder="e.g. facebook/react or vercel/next.js"
            required
          />
        </div>
        <button className="btn" type="submit" disabled={submitting}>
          {submitting ? "Starting…" : "Ingest"}
        </button>
      </form>

      <LoadingBanner phase={phase} runningLabel="Starting the ingest" />

      {error && <ErrorBox title="Couldn't start the ingest" message={error} />}

      {jobId && job.status === "running" && <JobStageBanner stage={job.stage} />}

      {jobId && job.status === "failed" && (
        <ErrorBox title="Ingest failed" message={job.error ?? "The ingest failed."} />
      )}

      {jobId && job.status === "succeeded" && result && (
        <div className="success-banner">
          {result.incremental ? "Incremental ingest complete. " : "Full ingest complete. "}
          Indexed {result.issues_indexed} issue{result.issues_indexed === 1 ? "" : "s"},{" "}
          {result.prs_indexed} merged PR{result.prs_indexed === 1 ? "" : "s"}, and{" "}
          {result.commits_indexed} commit{result.commits_indexed === 1 ? "" : "s"} (
          {result.total_newly_indexed} total).
        </div>
      )}
    </div>
  );
}
