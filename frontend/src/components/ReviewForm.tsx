import { useState } from "react";
import { ApiError, reviewPr } from "../api/client";
import type { ReviewResponse } from "../api/types";
import { useHealthAwareLoading } from "../hooks/useHealthAwareLoading";
import { LoadingBanner } from "./LoadingBanner";
import { ReviewResults } from "./ReviewResults";

export function ReviewForm({
  prefillRepo,
  prefillPr,
}: {
  prefillRepo?: string;
  prefillPr?: number;
}) {
  const [repo, setRepo] = useState(prefillRepo ?? "");
  const [prNumber, setPrNumber] = useState(prefillPr !== undefined ? String(prefillPr) : "");
  const [submittedRepo, setSubmittedRepo] = useState<string | null>(null);
  const { phase, run } = useHealthAwareLoading();
  const loading = phase !== "idle";
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReviewResponse | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    try {
      const data = await run(() => reviewPr(repo, Number(prNumber)));
      setResult(data);
      setSubmittedRepo(repo);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
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
        <button className="btn" type="submit" disabled={loading}>
          {loading ? "Reviewing…" : "Review PR"}
        </button>
      </form>

      <LoadingBanner phase={phase} runningLabel="Running review" />

      {error && <div className="error-banner">{error}</div>}

      {result && submittedRepo && !loading && <ReviewResults result={result} repo={submittedRepo} />}
    </div>
  );
}
