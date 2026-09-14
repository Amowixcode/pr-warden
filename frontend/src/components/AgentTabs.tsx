import { useRef, useState } from "react";
import type { AgentResult, Verdict } from "../api/types";
import type { AgentKey } from "../lib/attributeFindings";
import { FindingCard } from "./FindingCard";
import { StatusTag } from "./StatusTag";

const AGENTS: { key: AgentKey; label: string; dot: "sec" | "qua" | "tst" }[] = [
  { key: "security", label: "Security", dot: "sec" },
  { key: "quality", label: "Quality", dot: "qua" },
  { key: "test", label: "Test coverage", dot: "tst" },
];

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

/**
 * Per-agent results, keyed for AgentResult | null so ReviewDetail can pass through a missing
 * local join (Supabase has the review but the local per-agent store doesn't) without
 * fabricating a result.
 */
export interface AgentResults {
  security: AgentResult | null;
  quality: AgentResult | null;
  test: AgentResult | null;
}

export function AgentTabs({ results }: { results: AgentResults }) {
  const [active, setActive] = useState<AgentKey>("security");
  const tabRefs = useRef<Record<AgentKey, HTMLButtonElement | null>>({
    security: null,
    quality: null,
    test: null,
  });

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const i = AGENTS.findIndex((a) => a.key === active);
    const next = AGENTS[(i + (e.key === "ArrowRight" ? 1 : AGENTS.length - 1)) % AGENTS.length];
    setActive(next.key);
    tabRefs.current[next.key]?.focus();
  }

  return (
    <>
      <div className="tabs" role="tablist" onKeyDown={onKeyDown}>
        {AGENTS.map((agent) => {
          const result = results[agent.key];
          const isActive = active === agent.key;
          return (
            <button
              key={agent.key}
              ref={(el) => {
                tabRefs.current[agent.key] = el;
              }}
              type="button"
              className="tab"
              role="tab"
              aria-selected={isActive}
              aria-controls={`panel-${agent.key}`}
              id={`tab-${agent.key}`}
              tabIndex={isActive ? 0 : -1}
              onClick={() => setActive(agent.key)}
            >
              <span className={`dot dot-${agent.dot}`} />
              {agent.label}
              <span className="n">{result ? result.issues.length : "—"}</span>
            </button>
          );
        })}
      </div>

      {AGENTS.map((agent) => {
        const result = results[agent.key];
        return (
          <div
            key={agent.key}
            className="panel"
            role="tabpanel"
            id={`panel-${agent.key}`}
            aria-labelledby={`tab-${agent.key}`}
            hidden={active !== agent.key}
          >
            {result ? (
              <>
                <div className="panel-head">
                  <StatusTag color={VERDICT_DOT[result.verdict]} label={VERDICT_LABEL[result.verdict]} />
                  <p>{result.summary}</p>
                </div>
                {result.issues.length > 0 ? (
                  <ul className="findings">
                    {result.issues.map((text, i) => (
                      <FindingCard key={i} text={text} agent={agent.key} />
                    ))}
                  </ul>
                ) : (
                  <p className="api-key-note">No issues found.</p>
                )}
              </>
            ) : (
              <p className="api-key-note">Per-agent detail not available for this review.</p>
            )}
          </div>
        );
      })}
    </>
  );
}
