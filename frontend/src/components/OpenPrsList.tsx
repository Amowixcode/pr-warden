import { useState } from "react";
import { ApiError, listOpenPrs } from "../api/client";
import type { OpenPRResponse } from "../api/types";

export function OpenPrsList({ apiKey }: { apiKey: string }) {
  const [repo, setRepo] = useState("");
  const [loading, setLoading] = useState(false);
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
    setLoading(true);
    try {
      const data = await listOpenPrs(parts[0], parts[1], apiKey);
      setPrs(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load open PRs.");
    } finally {
      setLoading(false);
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
            placeholder="owner/repo"
            required
          />
        </div>
        <button className="btn" type="submit" disabled={loading}>
          {loading ? "Loading…" : "List open PRs"}
        </button>
      </form>

      {loading && (
        <div className="loading-banner">
          <span className="spinner" />
          Waking up the server — this can take up to a minute on the first request.
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}

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
                </tr>
              </thead>
              <tbody>
                {prs.map((pr) => (
                  <tr key={pr.number}>
                    <td className="mono">#{pr.number}</td>
                    <td>{pr.title}</td>
                    <td>{pr.author}</td>
                    <td>{pr.age_days}d</td>
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
