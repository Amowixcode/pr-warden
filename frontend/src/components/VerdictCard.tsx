import { attributeFindings } from "../lib/attributeFindings";
import type { AgentResult, Verdict } from "../api/types";
import type { DotColor } from "./StatusTag";
import { FindingCard } from "./FindingCard";
import { StatusTag } from "./StatusTag";
import { VerdictBadge } from "./VerdictBadge";

export function VerdictCard({
  repo,
  prNumber,
  verdict,
  summary,
  issues,
  agentResults,
  tags = [],
  headMeta,
  onRerun,
}: {
  repo: string;
  prNumber: number;
  verdict: Verdict;
  summary: string;
  issues: string[];
  agentResults: { security: AgentResult; quality: AgentResult; test: AgentResult };
  tags?: { color: DotColor; label: string }[];
  headMeta?: string;
  onRerun?: () => void;
}) {
  const attributed = attributeFindings(issues, agentResults);
  const totalPerAgent =
    agentResults.security.issues.length +
    agentResults.quality.issues.length +
    agentResults.test.issues.length;
  const isTruncated = issues.length < totalPerAgent;

  return (
    <div className="card verdict-card">
      <div className="card-head">
        <VerdictBadge verdict={verdict} />
        <span className="target">
          <a href={`https://github.com/${repo}/pull/${prNumber}`} target="_blank" rel="noreferrer">
            {repo}&nbsp;#{prNumber}
          </a>
        </span>
        {tags.map((tag) => (
          <StatusTag key={tag.label} color={tag.color} label={tag.label} />
        ))}
        {onRerun && (
          <button type="button" className="rerun-btn" onClick={onRerun}>
            Re-run
          </button>
        )}
        {headMeta && <span className="head-meta">{headMeta}</span>}
      </div>
      <div className="card-body">
        <p className="summary">{summary}</p>
        {attributed.length > 0 && (
          <>
            {isTruncated && (
              <p className="findings-label">
                Top {issues.length} of {totalPerAgent} findings
              </p>
            )}
            <ul className="findings">
              {attributed.map((finding, i) => (
                <FindingCard key={i} {...finding} />
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}
