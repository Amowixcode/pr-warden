import type { ReviewResponse } from "../api/types";
import { AgentTabs } from "./AgentTabs";
import { VerdictCard } from "./VerdictCard";

export function ReviewResults({
  result,
  repo,
  onRerun,
}: {
  result: ReviewResponse;
  repo: string;
  onRerun?: () => void;
}) {
  const tags = [];
  const notReviewed = result.not_reviewed ?? [];
  if (result.status === "nothing_new") {
    tags.push({ color: "ok" as const, label: "nothing new" });
  } else if (result.cached) {
    tags.push({ color: "ok" as const, label: "cached" });
  } else if (result.incremental) {
    tags.push({ color: "ok" as const, label: "incremental" });
  }

  return (
    <div>
      <VerdictCard
        repo={repo}
        prNumber={result.pr_number}
        verdict={result.verdict}
        summary={result.summary}
        issues={result.issues}
        agentResults={{
          security: result.security_result,
          quality: result.quality_result,
          test: result.test_result,
        }}
        tags={tags}
        onRerun={result.cached ? onRerun : undefined}
      />
      {result.status === "nothing_new" && <p className="api-key-note">{result.summary}</p>}
      {notReviewed.length > 0 && (
        <p className="api-key-note">Not reviewed: {notReviewed.join(", ")}</p>
      )}
      {result.cached && (
        <p className="api-key-note">
          No new commits since the last review — showing the cached verdict.
        </p>
      )}
      {result.incremental && !result.cached && result.status !== "nothing_new" && (
        <p className="api-key-note">Incremental review — prior verdict was {result.prior_verdict}.</p>
      )}

      <h2 className="label">What each agent found</h2>
      <AgentTabs
        results={{
          security: result.security_result,
          quality: result.quality_result,
          test: result.test_result,
        }}
      />
    </div>
  );
}
