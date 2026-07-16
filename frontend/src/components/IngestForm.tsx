import { useState } from "react";
import { ApiError, ingestRepository } from "../api/client";
import type { IngestResponse } from "../api/types";

export function IngestForm({ apiKey }: { apiKey: string }) {
  const [repo, setRepo] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const data = await ingestRepository(repo, apiKey);
      setResult(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setLoading(false);
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
            placeholder="owner/repo"
            required
          />
        </div>
        <button className="btn" type="submit" disabled={loading}>
          {loading ? "Ingesting…" : "Ingest"}
        </button>
      </form>

      {loading && (
        <div className="loading-banner">
          <span className="spinner" />
          Waking up the server — this can take up to a minute on the first request.
        </div>
      )}

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
