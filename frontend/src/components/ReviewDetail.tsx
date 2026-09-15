import { useEffect, useState } from "react";
import { ApiError, getReviewDetail } from "../api/client";
import type { ReviewDetail as ReviewDetailData } from "../api/types";
import { AgentTabs } from "./AgentTabs";
import { VerdictCard } from "./VerdictCard";

export function ReviewDetail({ id }: { id: number }) {
  const [review, setReview] = useState<ReviewDetailData | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setNotFound(false);
    setReview(null);

    getReviewDetail(id)
      .then((data) => {
        if (!cancelled) setReview(data);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
        } else {
          setError(err instanceof ApiError ? err.message : "Failed to load this review.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="loading-banner">
        <span className="spinner" />
        Loading review…
      </div>
    );
  }

  if (notFound) {
    return (
      <p className="api-key-note">
        Review not found. <a href="#/history">Back to history</a>
      </p>
    );
  }

  if (error) {
    return <div className="error-banner">{error}</div>;
  }

  if (!review) {
    return null;
  }

  return (
    <div>
      <p className="api-key-note">
        <a href="#/history">← Back to history</a>
      </p>
      <VerdictCard
        repo={review.repo}
        prNumber={review.pr_number}
        verdict={review.verdict}
        summary={review.summary}
        issues={review.issues}
        agentResults={{
          security: review.security_result ?? { summary: "", verdict: "APPROVE", issues: [], suggestions: [] },
          quality: review.quality_result ?? { summary: "", verdict: "APPROVE", issues: [], suggestions: [] },
          test: review.test_result ?? { summary: "", verdict: "APPROVE", issues: [], suggestions: [] },
        }}
      />

      <h2 className="label">What each agent found</h2>
      <AgentTabs
        results={{
          security: review.security_result,
          quality: review.quality_result,
          test: review.test_result,
        }}
      />
    </div>
  );
}
