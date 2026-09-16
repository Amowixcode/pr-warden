import { useState } from "react";
import { attributeFindings } from "../lib/attributeFindings";
import type { AgentResult, Verdict } from "../api/types";
import type { DotColor } from "./StatusTag";
import { FindingCard } from "./FindingCard";
import { StatusTag } from "./StatusTag";
import { VerdictBadge } from "./VerdictBadge";

const VISIBLE_COUNT = 3;

export function VerdictCard({
  repo,
  prNumber,
  verdict,
  summary,
  issues,
  agentResults,
  tags = [],
  headMeta,
  showMoreToggle = false,
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
  showMoreToggle?: boolean;
  onRerun?: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const attributed = attributeFindings(issues, agentResults);
  const totalPerAgent =
    agentResults.security.issues.length +
    agentResults.quality.issues.length +
    agentResults.test.issues.length;
  const isTruncated = issues.length < totalPerAgent;
  const paginate = showMoreToggle && attributed.length > VISIBLE_COUNT;
  const visible = paginate ? attributed.slice(0, VISIBLE_COUNT) : attributed;
  const rest = paginate ? attributed.slice(VISIBLE_COUNT) : [];

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
            {showMoreToggle
              ? paginate && (
                  <p className="count">
                    Showing {expanded ? attributed.length : VISIBLE_COUNT} of {attributed.length}
                  </p>
                )
              : isTruncated && (
                  <p className="findings-label">
                    Top {issues.length} of {totalPerAgent} findings
                  </p>
                )}
            <ul className="findings">
              {visible.map((finding, i) => (
                <FindingCard key={i} {...finding} />
              ))}
            </ul>
            {paginate && (
              <>
                <ul className="findings hidden-findings" hidden={!expanded}>
                  {rest.map((finding, i) => (
                    <FindingCard key={VISIBLE_COUNT + i} {...finding} />
                  ))}
                </ul>
                <button
                  type="button"
                  className="more"
                  aria-expanded={expanded}
                  onClick={() => setExpanded((e) => !e)}
                >
                  {expanded ? "Show fewer findings" : `Show ${rest.length} more findings`}
                </button>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
