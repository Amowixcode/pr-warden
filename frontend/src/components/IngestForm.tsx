import { useState } from "react";
import { ApiError, ingestRepository } from "../api/client";
import type { IngestResponse } from "../api/types";
import { useHealthAwareLoading } from "../hooks/useHealthAwareLoading";
import { LoadingBanner } from "./LoadingBanner";

export function IngestForm() {
  const [repo, setRepo] = useState("");
  const { phase, run } = useHealthAwareLoading();
  const loading = phase !== "idle";
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    try {
      const data = await run(() => ingestRepository(repo));
      setResult(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    }
  }

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
        <button className="btn" type="submit" disabled={loading}>
          {loading ? "Ingesting…" : "Ingest"}
        </button>
      </form>

      <LoadingBanner phase={phase} runningLabel="Ingesting" />

      {error && <div className="error-banner">{error}</div>}

      {result && !loading && (
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
