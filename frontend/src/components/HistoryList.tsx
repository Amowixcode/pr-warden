import { useEffect, useState } from "react";
import { ApiError, getReviewHistory } from "../api/client";
import type { ReviewHistoryItem } from "../api/types";
import { VerdictBadge } from "./VerdictBadge";

export function HistoryList({ apiKey }: { apiKey: string }) {
  const [items, setItems] = useState<ReviewHistoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getReviewHistory(apiKey)
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load history.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiKey]);

  if (loading) {
    return (
      <div className="loading-banner">
        <span className="spinner" />
        Loading review history…
      </div>
    );
  }

  if (error) {
    return <div className="error-banner">{error}</div>;
  }

  if (!items || items.length === 0) {
    return <p className="api-key-note">No reviews yet.</p>;
  }

  return (
    <table className="list-table">
      <thead>
        <tr>
          <th>Repo</th>
          <th>PR</th>
          <th>Verdict</th>
          <th>Summary</th>
          <th>Reviewed</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id}>
            <td className="mono">{item.repo}</td>
            <td className="mono">#{item.pr_number}</td>
            <td>
              <VerdictBadge verdict={item.verdict} />
            </td>
            <td>{item.summary}</td>
            <td>{new Date(item.created_at).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
