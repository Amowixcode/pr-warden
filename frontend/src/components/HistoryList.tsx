import { useEffect, useState } from "react";
import { ApiError, getReviewHistory } from "../api/client";
import type { ReviewHistoryItem, Verdict } from "../api/types";
import { StatusTag } from "./StatusTag";

const VERDICT_LABEL: Record<Verdict, string> = {
  APPROVE: "Approve",
  REQUEST_CHANGES: "Request changes",
  COMMENT: "Comment",
};

const VERDICT_DOT: Record<Verdict, "approve" | "request-changes" | "comment"> = {
  APPROVE: "approve",
  REQUEST_CHANGES: "request-changes",
  COMMENT: "comment",
};

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
    return (
      <p className="api-key-note">
        No reviews yet. Ingest a repo and review a PR to get started.
      </p>
    );
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
          <th>GitHub</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id}>
            <td className="mono">{item.repo}</td>
            <td className="mono">
              <a href={`#/review/${item.id}`}>#{item.pr_number}</a>
            </td>
            <td>
              <StatusTag color={VERDICT_DOT[item.verdict]} label={VERDICT_LABEL[item.verdict]} />
            </td>
            <td>{item.summary}</td>
            <td>{new Date(item.created_at).toLocaleString()}</td>
            <td>
              <a
                href={`https://github.com/${item.repo}/pull/${item.pr_number}`}
                target="_blank"
                rel="noreferrer"
              >
                View PR ↗
              </a>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
