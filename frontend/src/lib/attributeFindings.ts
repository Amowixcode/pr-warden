import type { AgentResult, ReviewResponse } from "../api/types";

export type AgentKey = "security" | "quality" | "test";

export interface AttributedFinding {
  text: string;
  agent: AgentKey | null;
}

/**
 * The merged `issues[]` on a ReviewResponse has no per-issue agent attribution — it's a flat,
 * possibly-truncated list. But the pipeline requires every issue to be a verbatim diff quote,
 * so the same string also appears in whichever per-agent `issues[]` produced it. Recovering
 * that attribution by exact membership needs no schema change and never fabricates anything —
 * an issue that matches no per-agent list (shouldn't happen, but isn't impossible) gets a null
 * agent, which callers render as an uncoloured card rather than a guessed one.
 */
export function attributeFindings(
  issues: string[],
  agentResults: { security: AgentResult; quality: AgentResult; test: AgentResult },
): AttributedFinding[] {
  const sets: [AgentKey, string[]][] = [
    ["security", agentResults.security.issues],
    ["quality", agentResults.quality.issues],
    ["test", agentResults.test.issues],
  ];
  return issues.map((text) => {
    const match = sets.find(([, agentIssues]) => agentIssues.includes(text));
    return { text, agent: match ? match[0] : null };
  });
}

export function attributeReviewFindings(result: ReviewResponse): AttributedFinding[] {
  return attributeFindings(result.issues, {
    security: result.security_result,
    quality: result.quality_result,
    test: result.test_result,
  });
}
