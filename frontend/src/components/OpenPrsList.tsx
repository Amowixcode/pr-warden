import { useState } from "react";
import { ApiError, listOpenPrs } from "../api/client";
import type { OpenPRResponse } from "../api/types";
import { useHealthAwareLoading } from "../hooks/useHealthAwareLoading";
import { LoadingBanner } from "./LoadingBanner";

export function OpenPrsList({
  apiKey,
  onReview,
}: {
  apiKey: string;
  onReview: (repo: string, prNumber: number) => void;
}) {
  const [repo, setRepo] = useState("");
  const [submittedRepo, setSubmittedRepo] = useState<string | null>(null);
  const { phase, run } = useHealthAwareLoading();
  const loading = phase !== "idle";
  const [error, setError] = useState<string | null>(null);
  const [prs, setPrs] = useState<OpenPRResponse[] | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const parts = repo.split("/");
    if (parts.length !== 2 || !parts[0] || !parts[1]) {
      setError("Expected 'owner/repo'.");
      return;
    }
    setError(null);
    setPrs(null);
    try {
      const data = await run(() => listOpenPrs(parts[0], parts[1], apiKey));
      setPrs(data);
      setSubmittedRepo(`${parts[0]}/${parts[1]}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load open PRs.");
    }
  }

  return (
    <div>
      <form className="card" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="prs-repo-input">Repository</label>
          <input
            id="prs-repo-input"
            className="mono"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            placeholder="e.g. facebook/react or vercel/next.js"
            required
          />
        </div>
        <button className="btn" type="submit" disabled={loading}>
          {loading ? "Loading…" : "List open PRs"}
        </button>
      </form>

      <LoadingBanner phase={phase} runningLabel="Loading open PRs" />

      {error && <div className="error-banner">{error}</div>}

      {prs === null && !loading && !error && (
        <p className="api-key-note">Enter a repo to see its open PRs.</p>
      )}

      {prs && !loading && (
        <>
          {prs.length === 0 ? (
            <p className="api-key-note">No open PRs.</p>
          ) : (
            <table className="list-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Title</th>
                  <th>Author</th>
                  <th>Age</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {prs.map((pr) => (
                  <tr key={pr.number}>
                    <td className="mono">
                      <a
                        href={`https://github.com/${submittedRepo}/pull/${pr.number}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        #{pr.number}
                      </a>
                    </td>
                    <td>{pr.title}</td>
                    <td>{pr.author}</td>
                    <td>{pr.age_days}d</td>
                    <td>
                      <button
                        type="button"
                        className="btn ghost"
                        onClick={() => submittedRepo && onReview(submittedRepo, pr.number)}
                      >
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}
