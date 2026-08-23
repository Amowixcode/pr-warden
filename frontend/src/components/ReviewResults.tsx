import type { AgentResult, ReviewResponse } from "../api/types";
import { VerdictBadge } from "./VerdictBadge";

function AgentSection({ title, result }: { title: string; result: AgentResult }) {
  return (
    <details className="agent-section">
      <summary>
        <span>{title}</span>
        <VerdictBadge verdict={result.verdict} />
      </summary>
      <div className="agent-body">
        <p>{result.summary}</p>
        {result.issues.length > 0 && (
          <ul className="issue-list">
            {result.issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
        )}
        {result.suggestions.length > 0 && (
          <ul className="suggestion-list">
            {result.suggestions.map((suggestion, i) => (
              <li key={i}>{suggestion}</li>
            ))}
          </ul>
        )}
      </div>
    </details>
  );
}

export function ReviewResults({ result }: { result: ReviewResponse }) {
  return (
    <div>
      <div className="card">
        <div className="btn-row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>
            Final Verdict — <span className="mono">#{result.pr_number}</span>
          </h2>
          <VerdictBadge verdict={result.verdict} />
        </div>
        <p>{result.summary}</p>
        {result.issues.length > 0 && (
          <ul className="issue-list">
            {result.issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
        )}
        {result.suggestions.length > 0 && (
          <ul className="suggestion-list">
            {result.suggestions.map((suggestion, i) => (
              <li key={i}>{suggestion}</li>
            ))}
          </ul>
        )}
        {result.cached && (
          <p className="api-key-note">
            No new commits since the last review — showing the cached verdict.
          </p>
        )}
        {result.incremental && !result.cached && (
          <p className="api-key-note">
            Incremental review — prior verdict was {result.prior_verdict}.
          </p>
        )}
      </div>

      <AgentSection title="Security" result={result.security_result} />
      <AgentSection title="Quality" result={result.quality_result} />
      <AgentSection title="Test Coverage" result={result.test_result} />
    </div>
  );
}
