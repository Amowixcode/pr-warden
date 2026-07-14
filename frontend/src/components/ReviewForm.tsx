import { useState } from "react";
import { ApiError, reviewPr } from "../api/client";
import type { ReviewResponse } from "../api/types";
import { ReviewResults } from "./ReviewResults";

export function ReviewForm({ apiKey }: { apiKey: string }) {
  const [repo, setRepo] = useState("");
  const [prNumber, setPrNumber] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReviewResponse | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const data = await reviewPr(repo, Number(prNumber), apiKey);
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
          <label htmlFor="repo-input">Repository</label>
          <input
            id="repo-input"
            className="mono"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            placeholder="owner/repo"
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
        <button className="btn" type="submit" disabled={loading}>
          {loading ? "Reviewing…" : "Review PR"}
        </button>
      </form>

      {loading && (
        <div className="loading-banner">
          <span className="spinner" />
          Waking up the server — this can take up to a minute on the first request.
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}

      {result && !loading && <ReviewResults result={result} />}
    </div>
  );
}
